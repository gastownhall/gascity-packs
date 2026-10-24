"""The two-dot vs three-dot diff base in mol-pr-ship (dr-46u9y).

`git diff A..B` is shorthand for `git diff A B`: a tree-to-tree comparison of
A's CURRENT tip against B. Once `origin/main` advances past the branch point
(any sibling PR merging while this one is in flight), every file main added
or changed since shows up as a deletion/reversion in a diff that is supposed
to mean "what this branch changed" -- and the docs gate that greps that diff
for `.md`/`docs/` fires on docs the branch never touched. `git diff A...B`
(three dots) diffs from the merge-base instead, matching GitHub's PR view.

Two sites in `mol-pr-ship.formula.toml` build a diff against a base branch
this way:
  - Stage 2 (`review-iterate`): the patch handed to the reviewer panel.
  - Stage 3 (`contributor-check`): the docs-gate membership test.

This file EXECUTES the real shell from those two sites against a fixture
git repo rather than asserting on the formula's text. Two dots is correct in
`git log` and `git rev-list`, so a text rule cannot tell a right use from a
wrong one; only running the line shows whether a reviewer sees deletions
nobody made.

Live mode: `PR_SHIP_FORMULA_VIA_GC=<dir>` loads the steps from
`gc formula show mol-pr-ship --json` run with cwd=<dir> instead of reading
this worktree's TOML, so the SAME assertions can be pointed at a city's
installed (possibly still-unfixed) copy of the formula.
"""
from __future__ import annotations

import functools
import json
import os
import pathlib
import re
import subprocess
import tempfile
import tomllib
import unittest

PACK_ROOT = pathlib.Path(__file__).resolve().parents[1]
FORMULA = PACK_ROOT / "formulas" / "mol-pr-ship.formula.toml"


# ---------------------------------------------------------------------------
# Step loading + anchor-based extraction (file mode or live `gc` mode)
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _load_steps() -> list[dict]:
    """Return the formula's steps as a list of {id, title, description, ...}.

    File mode reads this worktree's TOML directly. Live mode
    (`PR_SHIP_FORMULA_VIA_GC=<dir>`) shells out to the installed `gc` binary
    so the test can be pointed at a city's live, possibly-unfixed copy --
    the whole point being that this run must NOT be made to pass by editing
    the worktree; only fixing the live install fixes it.
    """
    via_gc = os.environ.get("PR_SHIP_FORMULA_VIA_GC")
    if via_gc:
        proc = subprocess.run(
            ["gc", "formula", "show", "mol-pr-ship", "--json"],
            cwd=via_gc, capture_output=True, text=True,
        )
        assert proc.returncode == 0, (
            f"gc formula show mol-pr-ship --json failed in {via_gc!r} "
            f"(rc={proc.returncode}): {proc.stderr}"
        )
        data = json.loads(proc.stdout)
    else:
        data = tomllib.loads(FORMULA.read_text(encoding="utf-8"))
    steps = data["steps"]
    assert steps, "mol-pr-ship reported zero steps"
    return steps


def _step(id_suffix: str) -> dict:
    """Find a step by id suffix.

    File-mode ids are bare (`review-iterate`); live `gc formula show --json`
    prefixes every step id with the formula name (`mol-pr-ship.review-iterate`).
    Matching on suffix works for both without caring which mode is active.
    """
    steps = _load_steps()
    matches = [s for s in steps if s["id"] == id_suffix or s["id"].endswith("." + id_suffix)]
    assert len(matches) == 1, (
        f"expected exactly one step id ending in {id_suffix!r}, found "
        f"{[s['id'] for s in steps]}"
    )
    return matches[0]


def _bash_block_after(text: str, anchor: str) -> str:
    """The contents of the first ```bash fence after a literal anchor string.

    Anchored on prose, not a line number -- a step's shell moves around as
    the formula's markdown is edited. Fails loudly, rather than extracting
    nothing, if the anchor or the fence is gone.
    """
    idx = text.find(anchor)
    assert idx != -1, f"anchor text vanished from the formula step: {anchor!r}"
    m = re.search(r"```bash\n(.*?)```", text[idx:], re.S)
    assert m, f"no ```bash block found after anchor {anchor!r}"
    return m.group(1)


def _patch_diff_line() -> str:
    """The exact `git diff <base> HEAD > <patch>` line from Stage 2."""
    block = _bash_block_after(
        _step("review-iterate")["description"],
        "Prepare the diff context for this iteration:",
    )
    m = re.search(r"^\s*(git diff origin/main\.{2,3}HEAD\s*>.*)$", block, re.M)
    assert m, f"the origin/main diff line vanished from the patch-prep block:\n{block}"
    return m.group(1).strip()


def _docs_gate_block() -> str:
    """The whole `if grep -q "^check-docs:" ... fi` block from Stage 3."""
    return _bash_block_after(
        _step("contributor-check")["description"],
        "### Docs (if Makefile has the target)",
    )


# ---------------------------------------------------------------------------
# Fixture git repo
# ---------------------------------------------------------------------------

def _fixture_env(tmp: pathlib.Path) -> dict:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp),
        "XDG_CONFIG_HOME": str(tmp / ".config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "pr-pipeline-test",
        "GIT_AUTHOR_EMAIL": "pr-pipeline-test@example.com",
        "GIT_COMMITTER_NAME": "pr-pipeline-test",
        "GIT_COMMITTER_EMAIL": "pr-pipeline-test@example.com",
    }


def _git(cwd: pathlib.Path, *args: str, env: dict) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed in {cwd}: {proc.stderr}"
    return proc


def _build_fixture(tmp: pathlib.Path) -> tuple[pathlib.Path, dict]:
    """A bare `origin`, a clone on `feature/one`, and `origin/main` advanced
    past the branch point by a sibling contributor while this branch was in
    flight.

    `feature/one` touches only `src/app.txt`. After the branch is cut, a
    second clone pushes a commit to `origin/main` that adds `docs/new.md`
    and edits `other.txt`. That is the exact trigger for the bug: a
    two-dot diff against origin/main's now-advanced tip makes those two
    files look like part of this PR (one as a deletion, one as a
    reversion), even though the branch never touched either.
    """
    env = _fixture_env(tmp)
    bare = tmp / "origin.git"
    _git(tmp, "init", "--bare", "-q", "-b", "main", str(bare), env=env)

    repo = tmp / "repo"
    _git(tmp, "clone", "-q", str(bare), str(repo), env=env)
    _git(repo, "checkout", "-q", "-B", "main", env=env)
    (repo / "README.md").write_text("root\n")
    (repo / "other.txt").write_text("v1\n")
    _git(repo, "add", "README.md", "other.txt", env=env)
    _git(repo, "commit", "-q", "-m", "init", env=env)
    _git(repo, "push", "-q", "-u", "origin", "main", env=env)
    _git(repo, "remote", "set-head", "origin", "-a", env=env)

    _git(repo, "checkout", "-q", "-b", "feature/one", env=env)
    (repo / "src").mkdir()
    (repo / "src" / "app.txt").write_text("feature change\n")
    _git(repo, "add", "src/app.txt", env=env)
    _git(repo, "commit", "-q", "-m", "feature: touch app.txt only", env=env)

    # A sibling contributor merges to origin/main while feature/one is open.
    other = tmp / "other-contributor"
    _git(tmp, "clone", "-q", str(bare), str(other), env=env)
    (other / "docs").mkdir()
    (other / "docs" / "new.md").write_text("new docs\n")
    (other / "other.txt").write_text("v2 -- changed by someone else\n")
    _git(other, "add", "docs/new.md", "other.txt", env=env)
    _git(other, "commit", "-q", "-m", "docs: add new.md; update other.txt", env=env)
    _git(other, "push", "-q", "origin", "main", env=env)

    # feature/one's clone learns origin/main has moved -- it never merges it.
    _git(repo, "fetch", "-q", "origin", env=env)
    return repo, env


def _add_docs_touching_branch(repo: pathlib.Path, env: dict) -> None:
    """A second branch, cut from the ALREADY-advanced origin/main, that
    genuinely edits a markdown file. The positive control: the docs gate
    must still fire for this one, proving the fix narrows the diff base
    rather than disabling the gate.
    """
    _git(repo, "checkout", "-q", "-b", "feature/docs-change", "origin/main", env=env)
    (repo / "docs" / "branch-notes.md").write_text("notes from this branch\n")
    _git(repo, "add", "docs/branch-notes.md", env=env)
    _git(repo, "commit", "-q", "-m", "docs: branch notes", env=env)


# ---------------------------------------------------------------------------
# Executing the extracted shell
# ---------------------------------------------------------------------------

def _run_patch_line(repo: pathlib.Path, env: dict, tmp: pathlib.Path,
                     branch: str = "feature/one", iter_n: str = "1") -> str:
    """Execute the Stage-2 patch line verbatim, redirected out of /tmp."""
    line = _patch_diff_line()
    exec_line = line.replace("/tmp/", f"{tmp}/out-")
    run_env = dict(env, BRANCH=branch, ITER_N=iter_n)
    proc = subprocess.run(["bash", "-c", exec_line], cwd=str(repo),
                           capture_output=True, text=True, env=run_env)
    assert proc.returncode == 0, (
        f"patch-diff line exited {proc.returncode}: {proc.stderr}\nline: {exec_line}"
    )
    safe_branch = branch.replace("/", "-")
    patch_path = tmp / f"out-pr-ship-{safe_branch}-iter{iter_n}.patch"
    assert patch_path.exists(), f"no patch written to {patch_path}\nline: {exec_line}"
    return patch_path.read_text()


def _run_docs_gate(repo: pathlib.Path, env: dict, branch: str) -> str:
    """Execute the Stage-3 docs-gate block verbatim and read back the
    GATES_PASSED / GATES_FAILED accumulators the real formula also uses."""
    block = _docs_gate_block()
    (repo / "Makefile").write_text("check-docs:\n\t@true\n")
    script = (
        'GATES_PASSED=""\nGATES_FAILED=""\n'
        + block
        + '\necho "PASSED=$GATES_PASSED"\necho "FAILED=$GATES_FAILED"\n'
    )
    _git(repo, "checkout", "-q", branch, env=env)
    proc = subprocess.run(["bash", "-c", script], cwd=str(repo),
                           capture_output=True, text=True, env=env)
    assert proc.returncode == 0, f"docs-gate block exited {proc.returncode}: {proc.stderr}"
    return proc.stdout


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class ReviewerPatchDiffBaseTests(unittest.TestCase):
    """Stage 2 -- the patch the reviewer panel actually reads."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmpdir.name)
        self.repo, self.env = _build_fixture(self.tmp)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_patch_contains_the_branchs_own_change(self) -> None:
        patch = _run_patch_line(self.repo, self.env, self.tmp)
        self.assertIn("app.txt", patch,
                       "the branch's own change is missing from its own patch")

    def test_patch_omits_mains_docs_commit(self) -> None:
        patch = _run_patch_line(self.repo, self.env, self.tmp)
        self.assertNotIn("new.md", patch,
                          "main's post-branch docs commit leaked into the PR patch as "
                          "a reviewable deletion -- this is the dr-46u9y bug")

    def test_patch_omits_mains_unrelated_edit(self) -> None:
        patch = _run_patch_line(self.repo, self.env, self.tmp)
        self.assertNotIn("changed by someone else", patch,
                          "main's post-branch edit to other.txt reads as part of this "
                          "PR's diff -- a reviewer would see it as a reversion nobody made")


class DocsGateDiffBaseTests(unittest.TestCase):
    """Stage 3 -- the mechanical gate that decides whether check-docs runs."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmpdir.name)
        self.repo, self.env = _build_fixture(self.tmp)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_gate_does_not_fire_for_a_branch_that_never_touched_docs(self) -> None:
        out = _run_docs_gate(self.repo, self.env, "feature/one")
        self.assertNotIn("docs", out,
                          f"the docs gate ran for a branch that only touched "
                          f"src/app.txt: {out!r}")

    def test_gate_still_fires_for_a_branch_that_really_touches_a_markdown_file(self) -> None:
        """The green rail -- without it, disabling the gate entirely would pass."""
        _add_docs_touching_branch(self.repo, self.env)
        out = _run_docs_gate(self.repo, self.env, "feature/docs-change")
        self.assertIn("PASSED= docs", out,
                       f"the docs gate did not fire for a branch that really added a "
                       f".md file -- the fix must narrow the base, not disable the gate: "
                       f"{out!r}")


if __name__ == "__main__":
    unittest.main()
