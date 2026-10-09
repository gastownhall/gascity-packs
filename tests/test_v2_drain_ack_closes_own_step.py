"""A v2 workflow step must close itself before `gc runtime drain-ack`.

Every step of a formula_compiler >= 2.0.0 workflow is a bead that a pool worker
claims with `gc hook --claim`, so the step an agent is running is in_progress
and assigned to its session. `gc runtime drain-ack` begins by releasing every
in_progress claim the session still holds (gascity
`releaseUnexecutedClaimsOnDrainAck`, #5265, effective for pool sessions since
#5505): a step that acks without closing itself is handed back to the pool,
open and still routed, a fresh session runs it again, and the workflow-finalize
control it blocks never fires.

So in every step checked here, each `gc runtime drain-ack` must be preceded, in
the same fenced bash block, by a fail-closed close of the step the session is
running: resolved with `gc hook current --id-only`, guarded on status and
`gc.step_ref`, and closed `|| exit 1`. This is the shape gascity's core
formulas use (gascity ga-51rapt; mol-do-work's drain step, #5153).

Mid-workflow early exits and root-only patrol formulas cannot be fixed by the
close alone and are pinned below as known exceptions, so a new drain-ack site
has to be classified rather than silently inheriting either list.
"""

from __future__ import annotations

from pathlib import Path
import re
import tomllib

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

# Steps whose every drain-ack must be preceded by the guarded own-step close.
# These are terminal steps: they block workflow-finalize directly, so closing
# them (gc.outcome=pass on success, fail on a halt) is sufficient on its own.
CHECKED_STEPS = {
    ("gastown/formulas/mol-polecat-work.toml", "submit-and-exit"),
    ("gastown/formulas/mol-review-leg.toml", "notify-close"),
    ("pr-pipeline/formulas/mol-pr-from-issue.formula.toml", "drain"),
}

# Mid-workflow early exits. Closing the step alone does not stop its
# dependents (a closed blocker satisfies `needs` whatever its gc.outcome), so
# these wait on the v2 early-abort idiom (scope + on_fail=abort_scope). Tracked
# in gascity; see the ga-uppw56 follow-ups. Remove an entry when it is fixed.
DEFERRED_STEPS = {
    ("gastown/formulas/mol-polecat-work.toml", "workspace-setup"),
    ("gastown/formulas/mol-polecat-work.toml", "self-review"),
    ("gastown/formulas/mol-review-leg.toml", "load-assignment"),
}

# v2 formulas whose steps are not beads: poured `--root-only` by a named
# session, so there is no step claim to close. Their drain-ack hazard is a
# different one (see the ga-uppw56 follow-ups).
EXEMPT_FORMULAS = {
    "gastown/formulas/mol-refinery-patrol.toml",
}

_OWN_STEP_CLOSE = re.compile(
    r'gc bd (?:update "\$([A-Z_]+)"[^\n]*--status[= ]closed|close "\$([A-Z_]+)")[^\n]*\|\| exit 1'
)


def bash_blocks(description: str) -> list[str]:
    blocks: list[str] = []
    block: list[str] = []
    in_bash = False
    for line in description.split("\n"):
        stripped = line.strip()
        if not in_bash and stripped.startswith("```bash"):
            in_bash, block = True, []
        elif in_bash and stripped == "```":
            in_bash = False
            blocks.append("\n".join(block))
        elif in_bash:
            block.append(line)
    return blocks


def drain_ack_violations(description: str, step_id: str) -> list[str]:
    """Every drain-ack line not preceded, in its own bash block, by a
    fail-closed, claim-resolved, step-guarded close of the running step."""
    violations = []
    for block in bash_blocks(description):
        lines = block.split("\n")
        for i, line in enumerate(lines):
            if "gc runtime drain-ack" not in line:
                continue
            preceding = "\n".join(lines[:i])
            closes_own_step = any(
                (m.group(1) or m.group(2)) != "WORK_BEAD_ID"
                for m in _OWN_STEP_CLOSE.finditer(preceding)
            )
            guarded = f'endswith(".{step_id}")' in preceding
            if "gc hook current --id-only" not in preceding or not closes_own_step or not guarded:
                violations.append(line.strip())
    return violations


def v2_formulas():
    for path in sorted(REPO_ROOT.glob("*/formulas/*.toml")):
        data = tomllib.loads(path.read_text())
        if "formula_compiler" in data.get("requires", {}):
            yield path.relative_to(REPO_ROOT).as_posix(), data


def drain_ack_steps():
    for rel, data in v2_formulas():
        for step in data.get("steps", []):
            if "gc runtime drain-ack" in step.get("description", ""):
                yield rel, step


def test_every_v2_drain_ack_step_is_classified():
    unclassified = [
        f"{rel}: {step['id']}"
        for rel, step in drain_ack_steps()
        if rel not in EXEMPT_FORMULAS
        and (rel, step["id"]) not in CHECKED_STEPS | DEFERRED_STEPS
    ]
    assert not unclassified, (
        "v2 formula steps run `gc runtime drain-ack` but are in no list above; "
        "a terminal step belongs in CHECKED_STEPS (and must close itself first): "
        + ", ".join(unclassified)
    )


@pytest.mark.parametrize("rel,step_id", sorted(CHECKED_STEPS))
def test_terminal_step_closes_itself_before_drain_ack(rel, step_id):
    data = tomllib.loads((REPO_ROOT / rel).read_text())
    steps = {s["id"]: s for s in data.get("steps", [])}
    assert step_id in steps, f"{rel} has no step {step_id}"
    description = steps[step_id]["description"]
    assert "gc runtime drain-ack" in description, f"{rel} {step_id} no longer drain-acks; drop it from CHECKED_STEPS"
    violations = drain_ack_violations(description, step_id)
    assert not violations, (
        f"{rel} {step_id}: drain-ack hands this still-claimed step back to the pool, "
        "so a fresh session re-runs it and the workflow never finalizes. Close the step "
        "the session is running first (gc hook current --id-only, guarded on in_progress "
        f"and a gc.step_ref ending .{step_id}, `|| exit 1`). Unguarded acks: {violations}"
    )


GUARDED = (
    'STEP_BEAD_ID=$(gc hook current --id-only) || exit 1\n'
    'STEP_BEAD=$(gc bd show "$STEP_BEAD_ID" --json) || exit 1\n'
    'printf \'%s\' "$STEP_BEAD" | jq -e \'.status == "in_progress" and ((.metadata["gc.step_ref"] // "") | endswith(".s"))\' >/dev/null || exit 1\n'
    'gc bd update "$STEP_BEAD_ID" --set-metadata gc.outcome=pass --status=closed || exit 1\n'
)


@pytest.mark.parametrize(
    "block,ok",
    [
        ("gc runtime drain-ack\nexit", False),
        ('gc bd close "$WORK_BEAD_ID" || exit 1\ngc runtime drain-ack', False),
        (
            'STEP_BEAD_ID=$(gc hook current --id-only) || exit 1\n'
            'gc bd update "$STEP_BEAD_ID" --status=closed\n'
            'gc runtime drain-ack',
            False,
        ),
        ('gc bd update "$STEP_BEAD_ID" --status=closed || exit 1\ngc runtime drain-ack', False),
        (
            'STEP_BEAD_ID=$(gc hook current --id-only) || exit 1\n'
            'gc bd update "$STEP_BEAD_ID" --status=closed || exit 1\n'
            'gc runtime drain-ack',
            False,
        ),
        (GUARDED + "gc runtime drain-ack", True),
        ('STEP_BEAD_ID=$(gc hook current --id-only) || exit 1\ngc runtime drain-ack\n' + GUARDED, False),
    ],
    ids=["bare", "work-bead-only", "not-fail-closed", "not-from-claim", "unguarded", "guarded", "ack-first"],
)
def test_checker_recognizes_the_guarded_close(block, ok):
    assert (not drain_ack_violations(f"```bash\n{block}\n```", "s")) == ok
