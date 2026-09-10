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
