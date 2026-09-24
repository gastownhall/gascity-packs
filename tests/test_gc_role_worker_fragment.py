"""Static checks on the shared `gc-role-worker` template fragment.

The rendered-prompt integration tests need a real gc binary (GC_TEST_BIN);
these run everywhere and pin the fragment text every role worker inherits.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRAGMENT = REPO_ROOT / "gascity" / "template-fragments" / "gc-role-worker.template.md"
README = REPO_ROOT / "gascity" / "README.md"


def fragment() -> str:
    return FRAGMENT.read_text(encoding="utf-8")


def test_fragment_defines_exactly_one_template() -> None:
    text = fragment()
    assert text.count('{{ define "gc-role-worker" -}}') == 1
    assert text.count("{{- end }}") == 1
    assert text.count("# GC Role Worker") == 1


def test_claim_section_tolerates_omitted_lifecycle_keys() -> None:
    text = fragment()
    claim = text.split("## Claim", 1)[1].split("## Workspace", 1)[0]
    assert "CLAIMED_ROOT_BEAD_ID" in claim
    assert "CLAIMED_CONTINUATION_GROUP" in claim
    assert "An absent key is an empty value, never a failed claim." in claim


def test_workspace_section_sits_between_claim_and_close() -> None:
    text = fragment()
    claim_at = text.index("## Claim")
    workspace_at = text.index("## Workspace")
    close_at = text.index("## Close")
    assert claim_at < workspace_at < close_at
    workspace = text[workspace_at:close_at]
    assert "$GC_DIR" in workspace
    assert "worker-worktree.sh" in workspace
    assert "if `git branch --show-current` prints" in workspace
    assert "restamp it when they differ" in workspace
    assert "--set-metadata 'work_dir=<absolute worktree path>'" in workspace
    assert "--set-metadata 'gc.work_branch=<branch>'" in workspace


def test_workspace_restamp_never_writes_over_a_recorded_item_branch() -> None:
    """Gate r9 on fork #32 (bead gp-d6gd): the claim-time compare-and-restamp
    rule is a writer of `gc.work_branch` too. Codex r1 on the bead: the
    fragment reads its own bead AFTER `gc hook --claim` stamped it, so no
    checkout state can tell a stamp from an item record. The operand is the
    NAME: the bead's branch is the one whose name contains the claimed bead
    id as a whole token (`pre_start` reused or created it), a record naming
    anything else is a stamp and the worker's branch wins, a record naming
    the bead is the branch the lane is on already, a branch the worker
    creates is named for the bead so the next `pre_start` finds it, and an
    empty value is never stamped. The fragment's one switch is the no-trigger
    take (codex r3), after the boundary test; a held branch closes
    `branch-held` instead of creating a second candidate."""
    workspace = " ".join(workspace_section().split())
    for clause in (
        "restamp it when they differ (older `gc` builds stamp the rig root's branch)",
        "The bead's branch is the one whose name contains the claimed bead id as a whole token",
        "the branch `pre_start` reused or created for it",
        "a record naming anything else is a claim-time stamp and your branch wins",
        "a record that names the bead is the branch you are on already (a held one closed above)",
        "Never write a fresh base branch over a recorded item branch",
        "never stamp an empty value",
        "name any branch you create for the claimed bead (`$CLAIMED_BEAD_ID` as a whole token) so the next `pre_start` finds it",
        "a branch of the bead recorded under a name without its id (from before this rule) is one for the mayor to rename, not for you to replace",
        # Codex r2: the pre_start WARN (the bead's branch held elsewhere, the
        # lane detached at its tip) must not produce a second candidate.
        "read that log first",
        "With no trigger bead the lane is detached at the base: take the claimed bead's branch after the claim, by the rule below, before committing anything",
        # Codex r3: a claim after a no-trigger pre_start must take the bead's
        # EXISTING branch by the same name rule, never create a second one.
        "A lane `pre_start` left detached because it had no trigger bead takes that branch itself, after the boundary test, the way `pre_start` would",
        "list every branch naming `$CLAIMED_BEAD_ID` as a whole token by full ref name",
        "`git -C \"$GC_DIR\" for-each-ref --format='%(refname)' refs/heads` with `refs/heads/` removed",
        "`refs/remotes/origin` with `refs/remotes/origin/` removed and `HEAD` dropped",
        'exactly one: `git -C "$GC_DIR" switch --no-overwrite-ignore <branch>`',
        "(`-c <branch> --track refs/remotes/origin/<branch>` when it is only on `origin`",
        "the start point by full ref, since a tag named `origin/<branch>` makes the bare form fail",
        'none: `git -C "$GC_DIR" switch -c "$CLAIMED_BEAD_ID"`',
        "several, or a refusal (another worktree holds it: `branch-held`, holder named from `git worktree list`): close the bead `gc.outcome=fail` and mail the mayor, never `--force`",
        "When the WARN says the bead's branch is checked out in another worktree, do not create a second branch naming the bead",
        "(two would make the next `pre_start` fail closed)",
        "close with `gc.outcome=fail` and `gc.failure_class=branch-held` naming that holder from `git worktree list`",
        "the next session's `pre_start` then reuses the branch and its commits",
    ):
        assert clause in workspace, f"the restamp rule lacks: {clause!r}"
    assert workspace.index("read that log first") < workspace.index("A session outside a gc-made lane")
    assert workspace.index("The bead's branch is the one whose name contains") < workspace.index("'gc.work_branch=<branch>'")
    # No checkout-state discriminator in the restamp rule; its one switch (the
    # no-trigger take) comes after the boundary test paragraph, and the old
    # "create your branch" advice that made a second candidate is gone.
    restamp = workspace[workspace.index("After the claim, compare") : workspace.index("'gc.work_branch=<branch>'")]
    for gone in ("default branch", "rig root's branch or", "rev-parse --verify", "refname:short"):
        assert gone not in restamp, f"the restamp rule consults checkout state: {gone!r}"
    assert workspace.index("Prove the lane before you write") < workspace.index("switch --no-overwrite-ignore <branch>")
    assert "create your branch in this directory" not in workspace


def test_workspace_section_never_names_the_rig_root_as_a_place_to_work() -> None:
    workspace = fragment().split("## Workspace", 1)[1].split("## Close", 1)[0]
    assert "never work in the rig root" in workspace
    assert "the rig root is a human\ncheckout" in workspace
    assert "cd " not in workspace


HUNTING_RULES = (
    ".worktrees/<rig>/<bead>",
    "create your\nown worktree",
    "create your own worktree",
    "create your worktree",
    "If you start in the rig root",
    "If `$GC_DIR` is the rig root",
    "worktree add",
)


def paragraphs(text: str) -> list[str]:
    """Blank-line separated paragraphs of a prompt, whitespace-stripped."""
    return [para.strip() for para in re.split(r"\n[ \t]*\n", text) if para.strip()]


def workspace_section() -> str:
    return fragment().split("## Workspace", 1)[1].split("## Close", 1)[0]


def role_prompts() -> list[Path]:
    return [FRAGMENT, *sorted((REPO_ROOT / "gascity" / "roles" / "agents").glob("*/prompt.template.md"))]


def test_workers_never_choose_or_create_their_workspace() -> None:
    """gc chooses the workspace (agent work_dir + pre_start). No role prompt
    tells a worker to go and make its own worktree, in ANY paragraph: the one
    conditional fallback that rounds 2 to 8 exempted here is gone (round 9,
    see test_session_outside_a_lane_creates_no_worktree_and_fails_closed_no_lane)."""
    workspace = workspace_section()
    assert "You never pick, create, or hunt for\na workspace" in workspace
    prompts = role_prompts()
    assert len(prompts) > 1
    for path in prompts:
        for para in paragraphs(path.read_text(encoding="utf-8")):
            for rule in HUNTING_RULES:
                assert rule not in para, (
                    f"{path.relative_to(REPO_ROOT)} tells the worker to make or hunt for a worktree: "
                    f"{rule!r} in {para[:60]!r}"
                )


def test_session_outside_a_lane_creates_no_worktree_and_fails_closed_no_lane() -> None:
    """Round 9 (Afik, 9/9 22:28 CT: "drop the fallback if we don't use it").
    Rounds 2, 3, 4, 7 and 8 each patched one paragraph that had a role the
    city gave no lane make its own worktree; no citadel dispatch takes that
    path since the city half went live. The fragment now carries NO
    worktree-creating instruction anywhere in its role-session text (no `git
    worktree add` verb, no `.worktrees/...` path to make, no base to resolve),
    and ONE paragraph says what a session outside a gc-made lane does: the
    three-part boundary test, then read by `git show` / `git log -1` only,
    and `gc.outcome=fail` + `gc.failure_class=no-lane` naming the lane the
    city must give the role. Grep-driven over the fragment and the README."""
    text = fragment()
    flat = " ".join(text.split())
    # No worktree-creating verb and no trace of the fallback, anywhere in the fragment.
    for gone in (
        "worktree add",
        ".worktrees/<rig>/<bead>",
        "create your worktree",
        "mail the mayor that this role needs a lane",
        "Resolve the base of a new branch",
        "<remote>/HEAD",
        "<remote>/main",
        "<remote>/master",
        "rev-parse --verify '<base>^{commit}'",
        "This fallback never fails",
        "If `$GC_DIR` is the rig root",
    ):
        assert gone not in flat, f"the fragment still carries the lane-less fallback: {gone!r}"
    assert "fallback" not in flat.lower()
    assert not any(para.startswith("If ") for para in paragraphs(workspace_section())), (
        "no conditional workspace paragraph: there is no fallback to condition"
    )

    # ONE paragraph for a session outside a lane, after the primary text.
    workspace = workspace_section()
    opener = "A session outside a gc-made lane has no lane"
    no_lane = [para for para in paragraphs(workspace) if para.startswith(opener)]
    assert len(no_lane) == 1, "exactly one no-lane paragraph"
    para = " ".join(no_lane[0].split())
    assert workspace.index("You never pick, create, or hunt for") < workspace.index(opener)
    # The three-part boundary test, in order, then the rule that depends on it.
    probes = (
        '`git -C "$GC_DIR" rev-parse --show-toplevel` is `$GC_DIR` itself',
        "that top-level is neither the rig root (`$GC_RIG_ROOT`) nor inside it",
        '`git -C "$GC_DIR" rev-parse --git-common-dir` is the rig root\'s `.git`',
    )
    positions = [para.index(probe) for probe in probes]
    assert positions == sorted(positions), para
    for clause in (
        "this role has no `work_dir` in your city",
        "Prove the lane before you write, with the three-part boundary test",
        "When any part fails (`$GC_DIR` is the rig root, a directory inside it, or a checkout of another repository)",
        "create no worktree and write nothing into the rig checkout: no `switch`, no detach, no branch, no commit there",
        'Read the item by `git -C "$GC_DIR" show <commit>:<path>` and `git -C "$GC_DIR" log -1 <commit>` only',
        "a step that needs a checkout closes the item with `gc.outcome=fail` and `gc.failure_class=no-lane`",
        "its close reason says in one line that the city must give this role a lane",
        "`[[patches.agent]]` with `work_dir` and `pre_start` in `city.toml`",
        "README, Worker workspaces",
        "A formula step whose own text creates the item's worktree (`do-work/prepare-worktree` in the rig root) runs unchanged",
    ):
        assert clause in para, f"the no-lane paragraph lacks: {clause!r}"
    assert positions[-1] < para.index("When any part fails") < para.index("`gc.failure_class=no-lane`")

    # README, Worker workspaces: the same rule, and no fallback left half-removed.
    readme = " ".join(README.read_text(encoding="utf-8").split())
    section = readme[readme.index("## Worker workspaces") : readme.index("## Build Methodology Contract")]
    assert "fallback" not in section.lower()
    assert ".worktrees/<rig>/<bead>" not in section
    for clause in (
        "A role the city gave no `work_dir` still starts in the rig root and has no lane",
        "the role prompt then has it create no worktree and write nothing there",
        "reads by `git show` and `git log` only",
        "closes with `gc.outcome=fail` and `gc.failure_class=no-lane`, naming the fix, a lane for the role",
        "No prompt-side path makes a workspace for an unconfigured role",
    ):
        assert clause in section, f"README Worker workspaces lacks: {clause!r}"


def test_worker_worktree_script_is_shipped_and_executable() -> None:
    script = REPO_ROOT / "gascity" / "assets" / "scripts" / "worker-worktree.sh"
    assert script.is_file()
    assert script.stat().st_mode & 0o111, "worker-worktree.sh must be executable"
    head = script.read_text(encoding="utf-8").splitlines()[0]
    assert head == "#!/bin/sh"


def test_workspace_section_gives_the_lane_to_one_agent_and_pins_it() -> None:
    """One lane, one agent (the per-agent work_dir model): the branch is the
    handoff, a helper session reads the lane and never writes into it, and
    the worker pins the lane with `gc session list` before its first write.
    Stated once, in the Workspace section, after the primary text."""
    workspace = workspace_section()
    opener = "The lane is yours alone"
    paras = [para for para in paragraphs(workspace) if para.startswith(opener)]
    assert len(paras) == 1, "exactly one lane-ownership paragraph"
    para = " ".join(paras[0].split())
    assert workspace.index("You never pick, create, or hunt for") < workspace.index(opener)
    assert workspace.index(opener) < workspace.index("A session outside a gc-made lane has no lane")
    for clause in (
        "one live session writes in a lane",
        "the branch, never the directory, is how work moves between agents",
        "reads this lane and writes nothing into it",
        "runs read-only here",
        "`git show <commit>:<path>`",
        "`gc session list` shows your session as the only live session whose work dir is `$GC_DIR`",
        "write nothing and mail the mayor naming both session ids",
    ):
        assert clause in para, f"lane-ownership paragraph lacks: {clause!r}"
    # README, Worker workspaces: the same rule.
    readme = " ".join(README.read_text(encoding="utf-8").split())
    section = readme.split("## Worker workspaces", 1)[1].split("## Worker toolchain", 1)[0]
    assert "A lane belongs to one live session at a time" in section
    assert "never writes into another agent's lane" in section


def test_readme_worker_toolchain_section_carries_the_recipe_and_the_decisions() -> None:
    """The toolchain wrappers are city runtime state with a pack source of
    record: the README installs both (node three times), keeps per-city
    settings in toolchain.env, records an md5 per file, states the pnpm 11
    measurement and the one-path lane install, says what the machine has and
    what the wrapper selects, and records the codex sandbox decision: the
    skip marker codex sets plus parent evidence, egress rejected."""
    text = README.read_text(encoding="utf-8")
    assert text.count("## Worker toolchain") == 1
    section = text.split("## Worker toolchain", 1)[1].split("## Build Methodology Contract", 1)[0]
    flat = " ".join(section.split())
    for clause in (
        'install -m 0755 path/to/gascity/assets/scripts/toolchain/pnpm "$CITY/.gc/shims/toolchain/pnpm"',
        'install -m 0755 path/to/gascity/assets/scripts/toolchain/node "$CITY/.gc/shims/toolchain/node"',
        'ln -sf node "$CITY/.gc/shims/toolchain/npm"',
        'ln -sf node "$CITY/.gc/shims/toolchain/npx"',
        "NODE_VERSION=24.21.0",
        "PNPM_VERSION=11.20.0",
        "show <pin>:gascity/assets/scripts/toolchain/pnpm > \"$canonical\" && md5 -q \"$canonical\"",
        "show <pin>:gascity/assets/scripts/toolchain/node > \"$canonical\" && md5 -q \"$canonical\"",
        'test "$(md5 -q "$CITY/.gc/shims/toolchain/pnpm")" = <that md5>',
        'test "$(md5 -q "$CITY/.gc/shims/toolchain/node")" = <that md5>',
        "`verify-deps-before-run` defaults to `install`",
        "`pnpm_config_verify_deps_before_run=false`",
        "`--config.verify-deps-before-run=error`",
        "In sync is pnpm's own word, never the wrapper's",
        "`node_modules/.gc-lane-deps.lock`",
        "`pnpm install --frozen-lockfile`",
        "concurrent callers wait for the lock and ask pnpm again",
        "A failed install fails the command",
        "Every change of hands of the lock goes through one gate, `.gc-lane-deps.lock.reclaim`",
        "leaving no lock standing",
        "a failed frozen install fails the command with pnpm's own exit status",
        "only the pid that took a lock releases it",
        "`GC_TOOLCHAIN_LANE_DEPS_INSTALLING=<lane>`",
        "Homebrew `node` is v25.9.0",
        "`toolchain.env` pins 24.21.0",
        "`CODEX_SANDBOX_NETWORK_DISABLED=1`",
        "`sandbox_workspace_write.network_access=true` is the egress switch, which a review must never gain",
        "`network.allow_local_binding=true`",
        "The alternative, network egress for the review, is rejected.",
        "`make test` at the repository root",
        "`make test-gascity`",
    ):
        assert clause in flat, f"README Worker toolchain lacks: {clause!r}"
    # each wrapper the README installs exists, executable, at the path it names
    for name in ("pnpm", "node"):
        path = REPO_ROOT / "gascity" / "assets" / "scripts" / "toolchain" / name
        assert path.is_file(), path
        assert path.stat().st_mode & 0o111, f"{path} is not executable"


def test_make_test_names_the_runner_a_worker_would_otherwise_rediscover() -> None:
    """`make test` / `make test-gascity` run pytest with the interpreter's own
    pytest or through `uv run --with pytest --with pyyaml --with jsonschema`,
    and unset GC_TEMPLATE, which a gc worker session exports."""
    import subprocess

    for target, dirs in (("test", "tests contributing/tests gascity/tests"), ("test-gascity", "tests gascity/tests")):
        out = subprocess.run(
            ["make", "-n", target], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout
        assert "env -u GC_TEMPLATE" in out
        assert "python3 -m pytest" in out
        assert "uv run --with pytest --with pyyaml --with jsonschema" in out
        assert dirs in out, out
    root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "make test            # every pytest suite CI runs" in root_readme
    assert "make test-gascity" in root_readme
