"""Real-git test of the lane handoff lifecycle the formula text prescribes.

The do-work and build-basic-review steps hand an item between agent lanes by
BRANCH (a directory is per agent). git allows one worktree per branch, so the
text fixes one lifecycle (gp-0mvp round 6, codex gate r5):

1. a WRITER (implement, the review fix lane) holds the item's branch only while
   writing and releases it with `git switch --detach` when it hands off;
2. a READER (the review lanes) never takes the branch: it detaches its own lane
   at the recorded commit, so parallel readers never contend;
3. the FIX lane takes the branch, commits, releases it; when a holder still has
   the branch it fails closed with the holder named and forces nothing;
4. a crashed writer's branch is released from that lane by the operator, never
   by another agent's step;
5. close-source-anchor reads `git log -1 refs/heads/<branch>` (the full ref
   since rule 11).

Round 7 (codex gate r6) adds two rules the loop's LATER attempts depend on:

6. the review setup runs ONCE, outside the review loop, and records the commit
   the readers inspect; the FIX lane refreshes that record after its commit
   and before it releases, so the next attempt's readers inspect the fix, not
   the original code;
7. every lane, reader or writer, proves it is a lane with the three-part
   boundary test before it switches or detaches anything; a reviewer role with
   no `work_dir` starts in the RIG ROOT (the human checkout), fails the test,
   detaches nothing, and inspects by `git show`/`git log` only.

Round 9 (Afik, 9/9 22:28 CT: "drop the fallback if we don't use it"; codex
gate r8) replaces round 8's lane-less workspace fallback and reshapes rule 6:

8. a role session outside a gc-made lane (a role the city gave no `work_dir`
   starts in the rig root, the human checkout) has no lane: it creates no
   worktree, creates and moves no branch, writes nothing into the rig
   checkout, reads the item by `git show` / `git log -1` only, and a step
   that needs a checkout closes `gc.outcome=fail`, `gc.failure_class=no-lane`;
9. the review commit is recorded PER SOURCE ANCHOR (`gc.review_commit` on the
   anchor, and the anchor's own record in the context file), never
   workflow-wide: separate drains put several items on independent branches,
   each inspected at its own commit, and a fix on one item leaves the others'
   recorded commits as they were.

Gate r9 on fork #32 (merged with this hole named; bead gp-d6gd) adds the rule
a re-launch depends on:

10. a re-launched item KEEPS its branch, found by NAME. `pre_start` names a
    lane's branch for the trigger STEP bead, so every new do-work run puts the
    operator's lane on a fresh step branch cut from the base, and a claim-time
    stamp can overwrite the recorded `gc.work_branch` with a name no checkout
    state can tell from an item branch (codex r1 on this bead: the rig root
    moves between branches, both directions leak). The one operand is the
    branch name: the item's branch is the one branch naming the source anchor
    id as a whole token, the rule `pre_start` applies to a claimed bead.
    prepare-worktree reads the record FIRST but lets it decide nothing (codex
    r2: a stamp can contain the id too): the one branch naming the item, in
    either namespace, is the branch; none means a new `<anchor>`; several
    fail closed for the operator to reconcile, the record among them or not.
    It takes the branch in its lane with git's one-worktree-per-branch
    refusal naming any holder, the rig root included, and records only when
    the record differs. A recorded item branch is never overwritten by a
    fresh base branch, so the committed work is where the next writer's
    switch lands.

Round 2 of gp-d6gd (the mayor's codex gate r1 on fork #34) adds the rule the
tag scenario of rule 10 stopped short of:

11. every read that resolves the item's branch NAME to a commit names the FULL
    ref, `refs/heads/<branch>`. git resolves a bare name tag-first
    (`refs/tags/<name>` before `refs/heads/<name>`), so with a tag of the
    branch's name at the base, `git log -1 <branch>` / `git rev-parse
    <branch>` / `git show <branch>` answer the BASE while `git switch
    <branch>` still takes the branch: close-source-anchor would have verified
    the base, the review setup would have recorded it as the commit under
    review, every review lane would have inspected it, and the fix lane's
    refresh would have re-recorded it. Only the branch operand of `git
    switch`, which resolves branches alone, stays bare (codex r5 on this
    round): a `--track` START POINT is a commit-ish, so the tracked take
    starts from `refs/remotes/origin/<branch>` (a tag named `origin/<branch>`
    makes the bare form fail "ambiguous object name"), and the fix lane's
    refresh reads `rev-parse --verify HEAD` of the worktree it committed in,
    which in the `work_dir` case is a detached per-item worktree with no item
    branch to read.

Every step below runs the exact git commands the formula text names, in real
worktrees under a temporary directory, with no network. The static rows in
test_formula_assets pin the sentences; this file pins that the sentences work.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile
import unittest


def git(cwd: pathlib.Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def out(cwd: pathlib.Path, *args: str) -> str:
    return git(cwd, *args).stdout.strip()


def commit(repo: pathlib.Path, name: str, content: str, message: str) -> str:
    (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", name)
    git(
        repo,
        "-c", "user.name=t", "-c", "user.email=t@example.invalid",
        "commit", "--quiet", "-m", message,
    )
    return out(repo, "rev-parse", "HEAD")


ITEM_BRANCH = "gp-item1"


class Rig:
    """A rig checkout (the human's) plus per-role lanes as worktrees of it,
    laid out the way the city's `work_dir = ".worktrees/{{.Rig}}/lane-..."`
    patch does. Each lane starts on its own step branch, as `pre_start`
    (worker-worktree.sh) leaves it: the step bead's branch, not the item's."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        self.rig = root / "rig"
        self.lanes_root = root / ".worktrees" / "rig"
        subprocess.run(["git", "init", "--quiet", "-b", "main", str(self.rig)], check=True)
        self.main_sha = commit(self.rig, "README.md", "hello\n", "init")
        self.rig_before = self.snapshot(self.rig)
        self.stderr_seen: list[str] = []

    def snapshot(self, checkout: pathlib.Path) -> tuple[str, str, str]:
        return (
            out(checkout, "branch", "--show-current"),
            out(checkout, "rev-parse", "HEAD"),
            out(checkout, "status", "--porcelain"),
        )

    def lane(self, role: str, step: str | None = None, *, detached: bool = False) -> pathlib.Path:
        path = self.lanes_root / f"lane-gc.{role}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if detached:
            # pre_start with no trigger bead: detached at the base.
            git(self.rig, "worktree", "add", "--quiet", "--detach", str(path), "main")
        else:
            # pre_start puts the lane on the STEP bead's branch, cut from HEAD.
            git(self.rig, "worktree", "add", "--quiet", "-b", step or f"step-{role}", str(path), "main")
        return path

    def pre_start(self, lane: pathlib.Path, step: str) -> None:
        """worker-worktree.sh on an EXISTING lane for a new trigger step bead:
        the script's `switch_worktree` in mode `new`, a fresh step branch cut
        from the base, whatever the lane held before. A re-launched run gets
        a new step id, so the same operator lane lands here on a branch that
        knows nothing of the item's earlier commits."""
        self.run(lane, "switch", "--quiet", "--no-overwrite-ignore", "-c", step, "main")
        assert out(lane, "branch", "--show-current") == step
        assert out(lane, "rev-parse", "HEAD") == self.main_sha

    def run(self, lane: pathlib.Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        proc = git(lane, *args, check=False)
        self.stderr_seen.append(proc.stderr)
        if check:
            assert proc.returncode == 0, f"git {' '.join(args)} in {lane.name}: {proc.stderr}"
        return proc

    def holder_of(self, branch: str) -> str | None:
        """The worktree path that has `branch` checked out, from
        `git worktree list --porcelain` (the command the fix lane names)."""
        current: str | None = None
        for line in out(self.rig, "worktree", "list", "--porcelain").splitlines():
            if line.startswith("worktree "):
                current = line[len("worktree "):]
            elif line == f"branch refs/heads/{branch}":
                return current
        return None

    # --- the lifecycle steps, each the formula text's commands ---------------

    def operator_prepares(self, lane: pathlib.Path, branch: str = ITEM_BRANCH) -> None:
        """prepare-worktree step 4, lane case: create the item's branch from HEAD
        (the lane was detached) and detach the lane from any branch. The
        branch is named for the source anchor; one per drained item."""
        self.run(lane, "switch", "--detach")  # the operator's lane starts detached here
        assert out(lane, "branch", "--show-current") == ""
        self.run(lane, "branch", branch, "HEAD")
        self.run(lane, "switch", "--detach")
        assert out(lane, "rev-parse", "--verify", f"refs/heads/{branch}")
        assert out(lane, "branch", "--show-current") == ""

    def writer_takes(
        self, lane: pathlib.Path, branch: str = ITEM_BRANCH, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """implement / apply-review-findings: switch the OWN lane onto the branch."""
        return self.run(lane, "switch", "--no-overwrite-ignore", branch, check=check)

    def writer_releases(self, lane: pathlib.Path) -> None:
        """Rule 1: after the final commit, before the close."""
        self.run(lane, "switch", "--detach")
        assert out(lane, "branch", "--show-current") == ""

    def close_verifies(self, lane: pathlib.Path, branch: str = ITEM_BRANCH) -> str:
        """close-source-anchor, from ITS OWN lane (rules 5 and 11): the
        implementation commit is the branch's tip, read by FULL ref
        (`git -C "$GC_DIR" log -1 "refs/heads/<gc.work_branch>"`); a bare
        name would answer a tag of the same name first."""
        return out(lane, "log", "-1", "--format=%H", f"refs/heads/{branch}")

    # --- rule 10 (gate r9): a re-launched item keeps its branch, found by NAME ---

    WORK_BRANCH_KEY = "gc.work_branch"

    @staticmethod
    def names_item(branch: str, anchor: str) -> bool:
        """worker-worktree.sh's "Bead branch" rule: the id as a whole token
        (`gp-abc1`, `fix/gp-abc1-x`, never `gp-abc10`)."""
        return re.search(r"(^|[^A-Za-z0-9])" + re.escape(anchor) + r"([^A-Za-z0-9]|$)", branch) is not None

    def item_branches(self, anchor: str) -> list[str]:
        """Every branch, local or on origin, whose name contains the anchor id
        as a whole token, one namespace at a time as the text and the script
        do: local names as printed (a local branch literally named `origin/x`
        keeps its name), remote names with exactly the leading `origin/`
        removed and `origin/HEAD` dropped; de-duplicated."""
        names: set[str] = set()
        for ref in out(self.rig, "for-each-ref", "--format=%(refname)", "refs/heads").splitlines():
            name = ref[len("refs/heads/"):]
            if self.names_item(name, anchor):
                names.add(name)
        for ref in out(self.rig, "for-each-ref", "--format=%(refname)", "refs/remotes/origin").splitlines():
            name = ref[len("refs/remotes/origin/"):]
            if name == "HEAD":
                continue
            if self.names_item(name, anchor):
                names.add(name)
        return sorted(names)

    def branch_exists(self, lane: pathlib.Path, branch: str) -> str:
        """'local', 'remote' or '' for a branch name, the way step 4 probes it."""
        if git(lane, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0:
            return "local"
        if git(lane, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}", check=False).returncode == 0:
            return "remote"
        return ""

    def operator_resolves_branch(
        self, lane: pathlib.Path, anchor_metadata: dict[str, str], anchor: str = ITEM_BRANCH, *, keep: bool = False
    ) -> dict[str, object]:
        """prepare-worktree step 4, lane case, after the boundary test, on the
        lane `pre_start` left on a fresh STEP branch. The item's branch is
        found by NAME (the one branch naming the anchor as a whole token);
        the record is read first, decides nothing on its own (codex r2: a
        stamp can contain the id), and is re-aligned when stale; no checkout
        state (the rig root's branch, a default branch) is consulted.

        1. exactly one branch names the item        -> BRANCH = that one
           none                                     -> BRANCH = <anchor>, new
           several (the record among them or not)   -> FAIL CLOSED, list them
        2. take BRANCH in this lane (--no-overwrite-ignore; -c for a new or
           origin-only branch); any refusal fails closed: a holder (ANY other
           worktree, the rig root included) is named, an ignored-file
           refusal names none and quotes git.
        Record only when the record differs from BRANCH; then release.
        """
        recorded = anchor_metadata.get(self.WORK_BRANCH_KEY, "")
        candidates = self.item_branches(anchor)
        if len(candidates) > 1:
            return {"gc.outcome": "fail", "failure": "several", "candidates": candidates}
        branch, chosen_by = (candidates[0], "name") if candidates else (anchor, "new")
        where = self.branch_exists(lane, branch)
        if chosen_by == "name" and not where:
            # Listed a moment ago, gone now: never fall through to `-c`.
            return {"gc.outcome": "fail", "failure": "vanished", "branch": branch}
        if where == "local":
            took = self.run(lane, "switch", "--no-overwrite-ignore", branch, check=False)
        elif where == "remote":
            took = self.run(lane, "switch", "--no-overwrite-ignore", "-c", branch, "--track", f"refs/remotes/origin/{branch}", check=False)
        else:
            took = self.run(lane, "switch", "--no-overwrite-ignore", "-c", branch, check=False)
        if took.returncode != 0:
            holder = self.holder_of(branch)
            if holder is not None:
                reason = f"branch {branch} is held at {holder}; the run operator releases it from that checkout"
            else:
                reason = f"git refused to take {branch}: {took.stderr.strip()}"
            return {
                "gc.outcome": "fail",
                "failure": "held" if holder is not None else "refused",
                "branch": branch,
                "holder": holder,
                "git": took.stderr,
                "reason": reason,
            }
        if recorded != branch:
            anchor_metadata[self.WORK_BRANCH_KEY] = branch
        assert anchor_metadata[self.WORK_BRANCH_KEY] == branch
        assert out(lane, "rev-parse", "--verify", f"refs/heads/{branch}")
        if keep:
            # The role fragment's claim-time take: the claiming worker is the
            # WRITER and stays on the branch until its own release.
            assert out(lane, "branch", "--show-current") == branch
        else:
            self.run(lane, "switch", "--detach")
            assert out(lane, "branch", "--show-current") == ""
        return {"gc.outcome": "pass", "chosen_by": chosen_by, "branch": branch, "recorded": recorded != branch}

    # --- round 7: the recorded commit and the boundary test ------------------

    REVIEW_COMMIT_KEY = "gc.review_commit"

    def setup_records(self, lane: pathlib.Path, anchors: list[str]) -> tuple[pathlib.Path, dict[str, dict[str, str]]]:
        """setup-build-basic-review, from ITS OWN lane: one record PER SOURCE
        ANCHOR in the review context file (the anchor id, its branch, the
        branch's commit, the changed files), and `gc.review_commit` on EACH
        source anchor (the anchors' metadata modelled as a dict per anchor id:
        the bead store is not part of this test). Nothing is recorded on the
        workflow root. The branch is named for the source anchor, and its
        commit is read by FULL ref (rule 11): a bare name would answer a tag
        of the same name first."""
        context = self.root / "artifacts" / "code-review-context.md"
        context.parent.mkdir(parents=True, exist_ok=True)
        records = []
        anchor_metadata: dict[str, dict[str, str]] = {}
        for anchor in anchors:
            commit_id = out(lane, "rev-parse", "--verify", f"refs/heads/{anchor}")
            changed = out(lane, "diff-tree", "--no-commit-id", "--name-only", "-r", commit_id)
            records.append(f"anchor: {anchor}\nbranch: {anchor}\ncommit: {commit_id}\nchanged_files: {changed}\n")
            anchor_metadata[anchor] = {self.REVIEW_COMMIT_KEY: commit_id}
        context.write_text("\n".join(records), encoding="utf-8")
        return context, anchor_metadata

    @staticmethod
    def context_records(context: pathlib.Path) -> dict[str, dict[str, str]]:
        """The context file's records, keyed by source anchor id."""
        records: dict[str, dict[str, str]] = {}
        for block in context.read_text(encoding="utf-8").split("\n\n"):
            fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
            if "anchor" in fields:
                records[fields["anchor"]] = fields
        return records

    @staticmethod
    def context_commit(context: pathlib.Path, anchor: str) -> str:
        record = Rig.context_records(context).get(anchor)
        if record is None or "commit" not in record:
            raise AssertionError(f"no record for {anchor} in the review context")
        return record["commit"]

    @staticmethod
    def reader_reads_current_commit(
        context: pathlib.Path, anchor_metadata: dict[str, dict[str, str]], anchor: str
    ) -> str:
        """A review lane, for ONE source anchor: `gc.review_commit` on that
        anchor first, that anchor's record in the context file only when the
        key is absent. No workflow-wide key exists to read."""
        return anchor_metadata.get(anchor, {}).get(Rig.REVIEW_COMMIT_KEY) or Rig.context_commit(context, anchor)

    def fix_lane_refreshes(
        self, lane: pathlib.Path, context: pathlib.Path, anchor_metadata: dict[str, dict[str, str]], anchor: str
    ) -> str:
        """apply-review-findings, after its fix commit and BEFORE the release:
        rewrite the commit id and changed files in the record of the source
        anchor it committed on, then record the new commit on that anchor.
        Every other anchor's record and key are left untouched. The new
        commit is HEAD of the worktree the fix was committed in (rule 11,
        codex r5): in the lane case that lane still holds the branch, so it
        is the branch's tip by FULL ref; a per-item `work_dir` worktree is
        detached and has no item branch to read."""
        new_commit = out(lane, "rev-parse", "--verify", "HEAD")
        held = out(lane, "branch", "--show-current")
        if held:
            assert new_commit == out(lane, "rev-parse", "--verify", f"refs/heads/{held}"), "the fix lane holds the branch it refreshes"
        changed = out(lane, "diff-tree", "--no-commit-id", "--name-only", "-r", new_commit)
        blocks = context.read_text(encoding="utf-8").split("\n\n")
        for index, block in enumerate(blocks):
            if f"anchor: {anchor}\n" not in block + "\n":
                continue
            lines = []
            for line in block.splitlines():
                if line.startswith("commit: "):
                    line = f"commit: {new_commit}"
                elif line.startswith("changed_files: "):
                    line = f"changed_files: {changed}"
                lines.append(line)
            blocks[index] = "\n".join(lines) + ("\n" if block.endswith("\n") else "")
        context.write_text("\n\n".join(blocks), encoding="utf-8")
        anchor_metadata.setdefault(anchor, {})[self.REVIEW_COMMIT_KEY] = new_commit
        return new_commit

    @staticmethod
    def boundary_test(gc_dir: pathlib.Path, rig_root: pathlib.Path) -> tuple[bool, bool, bool]:
        """prepare-worktree step 4, the three parts, every path resolved:
        1. the top-level of $GC_DIR IS $GC_DIR; 2. it is neither the rig root
        nor inside it; 3. its git common dir is the rig root's `.git`."""
        gc_dir_resolved = gc_dir.resolve()
        rig_resolved = rig_root.resolve()
        toplevel = pathlib.Path(out(gc_dir, "rev-parse", "--show-toplevel")).resolve()
        part1 = toplevel == gc_dir_resolved
        part2 = toplevel != rig_resolved and not str(toplevel).startswith(str(rig_resolved) + "/")
        common = pathlib.Path(out(gc_dir, "rev-parse", "--git-common-dir"))
        if not common.is_absolute():
            common = gc_dir / common
        rig_common = pathlib.Path(out(rig_root, "rev-parse", "--git-common-dir"))
        if not rig_common.is_absolute():
            rig_common = rig_root / rig_common
        part3 = common.resolve() == rig_common.resolve()
        return part1, part2, part3

    def reader_detaches(self, lane: pathlib.Path, commit_id: str) -> subprocess.Popen[str]:
        """Rule 2: a review lane inspects the recorded commit detached; returned
        as a process so two readers can do it at the same time."""
        return subprocess.Popen(
            ["git", "-C", str(lane), "switch", "--detach", "--no-overwrite-ignore", commit_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


    # --- round 9: a role session outside a lane ------------------------------

    @staticmethod
    def repository_state(checkout: pathlib.Path) -> dict[str, object]:
        """Everything a session could have moved: every file under the
        checkout (its `.git` aside), the checkout's HEAD, every ref, and the
        worktree list. Equal before and after means byte-identical."""
        files = {
            str(path.relative_to(checkout)): path.read_bytes()
            for path in sorted(checkout.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(checkout).parts
        }
        return {
            "files": files,
            "head": (checkout / ".git" / "HEAD").read_bytes(),
            "refs": out(checkout, "for-each-ref"),
            "worktrees": out(checkout, "worktree", "list", "--porcelain"),
            "branch": out(checkout, "branch", "--show-current"),
            "status": out(checkout, "status", "--porcelain"),
        }

    def session_without_lane(
        self, gc_dir: pathlib.Path, commit_id: str, path: str, *, needs_checkout: bool
    ) -> tuple[dict[str, str], str, str]:
        """The role prompt's Workspace paragraph for a session outside a
        gc-made lane: the boundary test fails, so no switch, no detach, no
        branch, no commit and no worktree; the item is read by `git show` /
        `git log -1` only, and a step that needs a checkout closes
        `gc.outcome=fail`, `gc.failure_class=no-lane`, naming the fix."""
        assert not all(self.boundary_test(gc_dir, self.rig)), "this is a lane"
        content = out(gc_dir, "show", f"{commit_id}:{path}")
        seen = out(gc_dir, "log", "-1", "--format=%H", commit_id)
        if needs_checkout:
            return (
                {
                    "gc.outcome": "fail",
                    "gc.failure_class": "no-lane",
                    "reason": "no lane for this role: the city must give it one ([[patches.agent]] work_dir + pre_start in city.toml)",
                },
                content,
                seen,
            )
        return {"gc.outcome": "pass"}, content, seen


class LaneLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.rig = Rig(pathlib.Path(self._tmp.name).resolve())

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def assert_rig_root_untouched(self) -> None:
        self.assertEqual(self.rig.snapshot(self.rig.rig), self.rig.rig_before)

    def assert_no_contention(self) -> None:
        for err in self.rig.stderr_seen:
            self.assertNotIn("already checked out", err)
            self.assertNotIn("already used by worktree", err)

    def test_hold_while_writing_release_on_handoff_inspect_detached(self) -> None:
        rig = self.rig
        operator = rig.lane("run-operator")
        implement = rig.lane("implementation-worker-1")
        reviewer_a = rig.lane("implementation-reviewer-1")
        reviewer_b = rig.lane("implementation-reviewer-2")
        fix = rig.lane("implementation-worker-2")

        # prepare-worktree (operator lane): the branch exists, the lane is detached.
        rig.operator_prepares(operator)
        self.assertEqual(out(operator, "branch", "--show-current"), "")

        # implement (its own lane): take, commit, RELEASE (rule 1).
        rig.writer_takes(implement)
        self.assertEqual(out(implement, "branch", "--show-current"), ITEM_BRANCH)
        impl_commit = commit(implement, "feature.txt", "implemented\n", "implement")
        rig.writer_releases(implement)
        self.assertEqual(out(implement, "rev-parse", "HEAD"), impl_commit)  # HEAD stays
        self.assertIsNone(rig.holder_of(ITEM_BRANCH))  # the branch is free
        self.assertEqual(out(operator, "branch", "--show-current"), "")

        # close-source-anchor / review setup read the commit by branch (rule 5).
        recorded = out(reviewer_a, "rev-parse", "--verify", f"refs/heads/{ITEM_BRANCH}")
        self.assertEqual(recorded, impl_commit)
        self.assertEqual(rig.close_verifies(reviewer_a), impl_commit)

        # TWO reviewers detach at the recorded commit at the same time (rule 2).
        procs = [rig.reader_detaches(reviewer_a, recorded), rig.reader_detaches(reviewer_b, recorded)]
        for proc in procs:
            _, err = proc.communicate(timeout=60)
            rig.stderr_seen.append(err)
            self.assertEqual(proc.returncode, 0, err)
        for reviewer in (reviewer_a, reviewer_b):
            self.assertEqual(out(reviewer, "branch", "--show-current"), "")
            self.assertEqual(out(reviewer, "rev-parse", "HEAD"), recorded)
            self.assertEqual(out(reviewer, "show", f"{recorded}:feature.txt"), "implemented")
            self.assertEqual((reviewer / "feature.txt").read_text(encoding="utf-8"), "implemented\n")
        self.assertIsNone(rig.holder_of(ITEM_BRANCH))  # readers never took it
        self.assertEqual(out(operator, "branch", "--show-current"), "")

        # apply-review-findings (a third lane): the branch is free; take, commit, release (rule 3).
        rig.writer_takes(fix)
        self.assertEqual(rig.holder_of(ITEM_BRANCH), str(fix))
        fix_commit = commit(fix, "feature.txt", "implemented\nfixed\n", "fix")
        rig.writer_releases(fix)
        self.assertIsNone(rig.holder_of(ITEM_BRANCH))

        # The close reads the branch tip: the fix commit, on top of the implementation.
        self.assertEqual(rig.close_verifies(operator), fix_commit)
        self.assertEqual(out(operator, "rev-parse", f"{fix_commit}^"), impl_commit)
        # Reviewers still sit at the commit they inspected; nothing moved under them.
        for reviewer in (reviewer_a, reviewer_b):
            self.assertEqual(out(reviewer, "rev-parse", "HEAD"), impl_commit)

        self.assert_no_contention()
        self.assertEqual(out(operator, "branch", "--show-current"), "")
        self.assert_rig_root_untouched()

    def test_writer_that_did_not_release_blocks_the_fix_lane_with_the_holder_named(self) -> None:
        rig = self.rig
        operator = rig.lane("run-operator")
        implement = rig.lane("implementation-worker-1")
        reviewer = rig.lane("implementation-reviewer-1")
        fix = rig.lane("implementation-worker-2")

        rig.operator_prepares(operator)
        rig.writer_takes(implement)
        impl_commit = commit(implement, "feature.txt", "implemented\n", "implement")
        # ... and the implementation lane crashes before `switch --detach`.
        self.assertEqual(rig.holder_of(ITEM_BRANCH), str(implement))

        # A reader is unaffected: it never wanted the branch.
        proc = rig.reader_detaches(reviewer, impl_commit)
        _, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out(reviewer, "show", f"{impl_commit}:feature.txt"), "implemented")

        # The fix lane's switch fails; git and `git worktree list` both name the holder.
        fix_before = rig.snapshot(fix)
        refused = rig.writer_takes(fix, check=False)
        self.assertNotEqual(refused.returncode, 0)
        # git < 2.45 says "already checked out at", newer says "already used by worktree at".
        self.assertRegex(refused.stderr + refused.stdout, r"already (checked out|used by worktree) at")
        self.assertIn(implement.name, refused.stderr + refused.stdout)
        self.assertEqual(rig.holder_of(ITEM_BRANCH), str(implement))

        # Nothing was forced: the fix lane is where it was, the holder still
        # holds, the operator lane is still detached, the rig root untouched.
        self.assertEqual(rig.snapshot(fix), fix_before)
        self.assertEqual(out(implement, "branch", "--show-current"), ITEM_BRANCH)
        self.assertEqual(out(implement, "rev-parse", "HEAD"), impl_commit)
        self.assertEqual(out(operator, "branch", "--show-current"), "")
        self.assert_rig_root_untouched()

        # Rule 4: the operator releases the branch FROM THE HOLDER'S LANE; only
        # then does the fix lane's own switch succeed.
        rig.run(implement, "switch", "--detach")
        self.assertIsNone(rig.holder_of(ITEM_BRANCH))
        rig.writer_takes(fix)
        self.assertEqual(rig.holder_of(ITEM_BRANCH), str(fix))
        fix_commit = commit(fix, "feature.txt", "implemented\nfixed\n", "fix")
        rig.writer_releases(fix)
        self.assertEqual(rig.close_verifies(operator), fix_commit)
        self.assert_rig_root_untouched()

    def test_detach_at_commit_refuses_to_overwrite_an_ignored_file(self) -> None:
        """The reader's `switch --detach --no-overwrite-ignore <commit>` keeps
        the round-5 guarantee: an ignored file in the lane that the commit
        tracks makes git refuse, and the lane is left as it was."""
        rig = self.rig
        operator = rig.lane("run-operator")
        implement = rig.lane("implementation-worker-1")
        reviewer = rig.lane("implementation-reviewer-1")

        rig.operator_prepares(operator)
        rig.writer_takes(implement)
        impl_commit = commit(implement, "build.out", "tracked\n", "implement tracks a build output")
        rig.writer_releases(implement)

        (reviewer / "build.out").write_text("ignored local\n", encoding="utf-8")
        info_exclude = pathlib.Path(out(reviewer, "rev-parse", "--git-path", "info/exclude"))
        info_exclude.parent.mkdir(parents=True, exist_ok=True)
        info_exclude.write_text("build.out\n", encoding="utf-8")
        self.assertEqual(out(reviewer, "status", "--porcelain"), "")  # ignored, not untracked

        before = rig.snapshot(reviewer)
        proc = rig.reader_detaches(reviewer, impl_commit)
        _, err = proc.communicate(timeout=60)
        self.assertNotEqual(proc.returncode, 0, "git overwrote an ignored file")
        self.assertIn("build.out", err)
        self.assertEqual(rig.snapshot(reviewer), before)
        self.assertEqual((reviewer / "build.out").read_text(encoding="utf-8"), "ignored local\n")
        self.assert_rig_root_untouched()

    def test_fix_lane_refreshes_the_recorded_commit_so_the_next_attempt_reviews_the_fix(self) -> None:
        """Rule 6 (gate r6 M1). The setup records commit A once; the fix lane
        commits B and refreshes the anchor's record in the context file and
        the anchor's key BEFORE it releases; a reader on the next attempt
        reads B (from the anchor's key first, from the anchor's record when
        the key is absent), detaches at B, and sees the fix. A is gone from
        the context. The rig root never changes."""
        rig = self.rig
        operator = rig.lane("run-operator")
        implement = rig.lane("implementation-worker-1")
        setup = rig.lane("run-operator-2")
        reviewer_1 = rig.lane("implementation-reviewer-1")
        fix = rig.lane("implementation-worker-2")
        reviewer_2 = rig.lane("implementation-reviewer-2")

        rig.operator_prepares(operator)
        rig.writer_takes(implement)
        commit_a = commit(implement, "feature.txt", "implemented\n", "implement")
        rig.writer_releases(implement)

        # setup-build-basic-review, ONCE, outside the loop: records A.
        context, anchors = rig.setup_records(setup, [ITEM_BRANCH])
        self.assertEqual(rig.context_commit(context, ITEM_BRANCH), commit_a)
        self.assertEqual(anchors, {ITEM_BRANCH: {"gc.review_commit": commit_a}})
        self.assertIn("changed_files: feature.txt", context.read_text(encoding="utf-8"))

        # Attempt 1: a reader reads A, detaches at A, finds the defect.
        current = rig.reader_reads_current_commit(context, anchors, ITEM_BRANCH)
        self.assertEqual(current, commit_a)
        proc = rig.reader_detaches(reviewer_1, current)
        _, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out(reviewer_1, "show", f"{current}:feature.txt"), "implemented")

        # apply-review-findings: take, commit B, REFRESH, then release.
        rig.writer_takes(fix)
        commit_b = commit(fix, "feature.txt", "implemented\nfixed\n", "fix")
        (fix / "feature_test.txt").write_text("proof\n", encoding="utf-8")
        git(fix, "add", "feature_test.txt")
        git(fix, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "--quiet", "--amend", "--no-edit")
        commit_b = out(fix, "rev-parse", "HEAD")
        self.assertNotEqual(commit_b, commit_a)
        refreshed = rig.fix_lane_refreshes(fix, context, anchors, ITEM_BRANCH)
        # The refresh happened while the fix lane still HOLDS the branch (before the release).
        self.assertEqual(rig.holder_of(ITEM_BRANCH), str(fix))
        self.assertEqual(refreshed, commit_b)
        rig.writer_releases(fix)

        # Never leave the old commit in the context after a fix.
        context_text = context.read_text(encoding="utf-8")
        self.assertNotIn(commit_a, context_text)
        self.assertEqual(rig.context_commit(context, ITEM_BRANCH), commit_b)
        self.assertIn("changed_files: feature.txt feature_test.txt", " ".join(context_text.split()))
        self.assertEqual(anchors[ITEM_BRANCH]["gc.review_commit"], commit_b)
        self.assertEqual(rig.close_verifies(operator), commit_b)

        # Attempt 2: a reader reads B, not A: from the anchor's key first ...
        current = rig.reader_reads_current_commit(context, anchors, ITEM_BRANCH)
        self.assertEqual(current, commit_b)
        # ... and from the anchor's record in the context file when the key is absent.
        self.assertEqual(rig.reader_reads_current_commit(context, {}, ITEM_BRANCH), commit_b)
        self.assertEqual(rig.reader_reads_current_commit(context, {ITEM_BRANCH: {}}, ITEM_BRANCH), commit_b)
        proc = rig.reader_detaches(reviewer_2, current)
        _, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out(reviewer_2, "rev-parse", "HEAD"), commit_b)
        self.assertEqual(out(reviewer_2, "show", f"{current}:feature.txt"), "implemented\nfixed")
        self.assertEqual((reviewer_2 / "feature_test.txt").read_text(encoding="utf-8"), "proof\n")
        # The round-6 shape (the stale commit) is what this rule removes: a
        # reader at A would not have seen the fix at all.
        self.assertEqual(out(reviewer_1, "show", f"{commit_a}:feature.txt"), "implemented")

        self.assertIsNone(rig.holder_of(ITEM_BRANCH))
        self.assert_no_contention()
        self.assert_rig_root_untouched()

    def test_reviewer_in_the_rig_root_never_detaches_the_human_checkout(self) -> None:
        """Rule 7 (gate r6 M2). A reviewer role with no configured `work_dir`
        starts in the RIG ROOT: `$GC_DIR` is the human checkout. The
        three-part boundary test fails there (part 2), in a subdirectory of
        the rig root (part 1) and in a worktree of another repository (part
        3), and holds in a real lane. Failing it, the reader detaches NOTHING
        and inspects by `git show <commit>:<path>` / `git log -1 <commit>`,
        which work from any checkout of the rig's repository. Last, the
        command the guard withholds is run once against the rig root to show
        what it would have done: moved the human checkout's HEAD."""
        rig = self.rig
        operator = rig.lane("run-operator")
        implement = rig.lane("implementation-worker-1")
        lane_reviewer = rig.lane("implementation-reviewer-1")

        rig.operator_prepares(operator)
        rig.writer_takes(implement)
        commit_a = commit(implement, "feature.txt", "implemented\n", "implement")
        rig.writer_releases(implement)
        recorded = out(implement, "rev-parse", "--verify", f"refs/heads/{ITEM_BRANCH}")
        self.assertEqual(recorded, commit_a)

        # Positive proof: a real lane passes all three parts.
        self.assertEqual(rig.boundary_test(lane_reviewer, rig.rig), (True, True, True))

        # The rig root itself: part 2 fails (it IS the rig root).
        rig_root_as_gc_dir = rig.rig
        self.assertEqual(rig.boundary_test(rig_root_as_gc_dir, rig.rig), (True, False, True))
        # A subdirectory of the human checkout: part 1 fails (and part 2).
        subdir = rig.rig / "src"
        subdir.mkdir()
        self.assertEqual(rig.boundary_test(subdir, rig.rig)[:2], (False, False))
        # A worktree of ANOTHER repository: parts 1 and 2 hold, part 3 fails.
        other = rig.root / "other-repo"
        subprocess.run(["git", "init", "--quiet", "-b", "main", str(other)], check=True)
        commit(other, "x.txt", "x\n", "other")
        self.assertEqual(rig.boundary_test(other, rig.rig), (True, True, False))

        # The reviewer whose $GC_DIR is the rig root: the test fails, so it
        # runs NO switch and NO detach there, and reads by show/log only.
        parts = rig.boundary_test(rig_root_as_gc_dir, rig.rig)
        self.assertFalse(all(parts))
        before = rig.snapshot(rig_root_as_gc_dir)
        self.assertEqual(out(rig_root_as_gc_dir, "show", f"{recorded}:feature.txt"), "implemented")
        self.assertEqual(out(rig_root_as_gc_dir, "log", "-1", "--format=%H", recorded), recorded)
        self.assertEqual(rig.snapshot(rig_root_as_gc_dir), before)
        self.assertEqual(out(rig_root_as_gc_dir, "branch", "--show-current"), "main")
        self.assertEqual(out(rig_root_as_gc_dir, "rev-parse", "HEAD"), rig.main_sha)
        self.assert_rig_root_untouched()
        # The lane reviewer, having passed, detaches at the commit as before.
        proc = rig.reader_detaches(lane_reviewer, recorded)
        _, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out(lane_reviewer, "rev-parse", "HEAD"), recorded)
        self.assert_rig_root_untouched()

        # What the guard withholds: the round-6 reader command, run in the rig
        # root, detaches the human checkout and moves its HEAD off main.
        proc = rig.reader_detaches(rig_root_as_gc_dir, recorded)
        _, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out(rig_root_as_gc_dir, "branch", "--show-current"), "")
        self.assertEqual(out(rig_root_as_gc_dir, "rev-parse", "HEAD"), recorded)
        self.assertNotEqual(rig.snapshot(rig_root_as_gc_dir), rig.rig_before)


    def test_role_session_without_a_lane_reads_detached_creates_no_worktree_and_moves_nothing(self) -> None:
        """Rule 8 (round 9; Afik: drop the fallback). A role the city gave no
        `work_dir` starts in the rig root: `$GC_DIR` is the human checkout and
        the boundary test fails. The session reads the item by `git show` /
        `git log -1` only, creates no worktree, creates and moves no branch,
        and a step that needs a checkout closes `gc.outcome=fail`,
        `gc.failure_class=no-lane` naming the fix. The rig checkout is
        byte-identical after: every file under it, its HEAD, every ref, the
        worktree list. Rounds 2 to 8 had this session make and enter
        `<city>/.worktrees/<rig>/<bead>` from here; that path is gone."""
        rig = self.rig
        operator = rig.lane("run-operator")
        implement = rig.lane("implementation-worker-1")
        rig.operator_prepares(operator)
        rig.writer_takes(implement)
        recorded = commit(implement, "feature.txt", "implemented\n", "implement")
        rig.writer_releases(implement)

        gc_dir = rig.rig  # a role with no lane: $GC_DIR is the rig root
        self.assertEqual(Rig.boundary_test(gc_dir, rig.rig), (True, False, True))
        before = rig.repository_state(gc_dir)
        self.assertEqual(before["worktrees"].count("worktree "), 3)  # the rig, the operator, the implementer

        # A read-only step: reads the item, closes pass.
        outcome, content, seen = rig.session_without_lane(gc_dir, recorded, "feature.txt", needs_checkout=False)
        self.assertEqual(outcome, {"gc.outcome": "pass"})
        self.assertEqual((content, seen), ("implemented", recorded))
        # A step that needs a checkout at the commit: fails closed, no-lane, names the fix.
        outcome, content, seen = rig.session_without_lane(gc_dir, recorded, "feature.txt", needs_checkout=True)
        self.assertEqual((outcome["gc.outcome"], outcome["gc.failure_class"]), ("fail", "no-lane"))
        self.assertIn("[[patches.agent]]", outcome["reason"])
        self.assertEqual((content, seen), ("implemented", recorded))

        # Nothing moved: no worktree, no branch, no detach, no file; byte-identical.
        after = rig.repository_state(gc_dir)
        self.assertEqual(after, before)
        self.assertEqual(after["worktrees"].count("worktree "), 3)
        self.assertEqual(out(gc_dir, "branch", "--show-current"), "main")
        self.assertEqual(out(gc_dir, "rev-parse", "HEAD"), rig.main_sha)
        self.assertFalse((gc_dir / "feature.txt").exists())  # the commit was read, never checked out
        self.assertEqual(sorted(path.name for path in rig.lanes_root.iterdir()), ["lane-gc.implementation-worker-1", "lane-gc.run-operator"])
        self.assertIsNone(rig.holder_of(ITEM_BRANCH))
        self.assert_no_contention()
        self.assert_rig_root_untouched()

    def test_two_source_anchors_keep_their_own_review_commits_when_one_is_fixed(self) -> None:
        """Rule 9 (gate r8 MAJOR). Two drains produce two source anchors on
        independent branches. The setup records each item's commit on ITS
        anchor; a fix on item 1 refreshes item 1's record and key only; item
        2's recorded commit is unchanged, and item 2's reader detaches at
        item 2's own revision, where item 1's files do not exist. One
        workflow-wide key (round 7's shape), overwritten by the fix, would
        have sent item 2's reader to item 1's fix commit."""
        rig = self.rig
        item_1, item_2 = "gp-item1", "gp-item2"
        operator = rig.lane("run-operator")
        impl_1 = rig.lane("implementation-worker-1")
        impl_2 = rig.lane("implementation-worker-2")
        setup = rig.lane("run-operator-2")
        reviewer_1 = rig.lane("implementation-reviewer-1")
        reviewer_2 = rig.lane("implementation-reviewer-2")
        fix = rig.lane("implementation-worker-3")

        # Two drains: two branches from main, two implementers, both released.
        rig.operator_prepares(operator, item_1)
        rig.operator_prepares(operator, item_2)
        rig.writer_takes(impl_1, item_1)
        a1 = commit(impl_1, "one.txt", "one\n", "implement item 1")
        rig.writer_releases(impl_1)
        rig.writer_takes(impl_2, item_2)
        a2 = commit(impl_2, "two.txt", "two\n", "implement item 2")
        rig.writer_releases(impl_2)
        self.assertNotEqual(a1, a2)
        # Independent branches: neither commit is an ancestor of the other.
        self.assertNotEqual(git(rig.rig, "merge-base", "--is-ancestor", a1, a2, check=False).returncode, 0)
        self.assertNotEqual(git(rig.rig, "merge-base", "--is-ancestor", a2, a1, check=False).returncode, 0)

        # setup-build-basic-review, ONCE: one record and one key per anchor.
        context, anchors = rig.setup_records(setup, [item_1, item_2])
        self.assertEqual(anchors, {item_1: {"gc.review_commit": a1}, item_2: {"gc.review_commit": a2}})
        self.assertEqual(rig.context_commit(context, item_1), a1)
        self.assertEqual(rig.context_commit(context, item_2), a2)
        self.assertEqual(rig.context_records(context)[item_2]["changed_files"], "two.txt")

        # apply-review-findings fixes item 1 ONLY: take, commit, refresh item 1's record, release.
        rig.writer_takes(fix, item_1)
        b1 = commit(fix, "one.txt", "one\nfixed\n", "fix item 1")
        self.assertEqual(rig.fix_lane_refreshes(fix, context, anchors, item_1), b1)
        rig.writer_releases(fix)

        # Item 1 moved to B1; item 2's record and key are exactly as the setup left them.
        self.assertEqual(anchors, {item_1: {"gc.review_commit": b1}, item_2: {"gc.review_commit": a2}})
        self.assertEqual(rig.context_commit(context, item_1), b1)
        self.assertEqual(rig.context_commit(context, item_2), a2)
        context_text = context.read_text(encoding="utf-8")
        self.assertNotIn(a1, context_text)
        self.assertIn(a2, context_text)
        self.assertEqual(rig.context_records(context)[item_2]["changed_files"], "two.txt")
        self.assertEqual(rig.close_verifies(operator, item_1), b1)
        self.assertEqual(rig.close_verifies(operator, item_2), a2)

        # Attempt 2: each reader reads ITS anchor's commit and inspects that revision.
        current_1 = rig.reader_reads_current_commit(context, anchors, item_1)
        current_2 = rig.reader_reads_current_commit(context, anchors, item_2)
        self.assertEqual((current_1, current_2), (b1, a2))
        for reviewer, current in ((reviewer_1, current_1), (reviewer_2, current_2)):
            proc = rig.reader_detaches(reviewer, current)
            _, err = proc.communicate(timeout=60)
            rig.stderr_seen.append(err)
            self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out(reviewer_1, "rev-parse", "HEAD"), b1)
        self.assertEqual((reviewer_1 / "one.txt").read_text(encoding="utf-8"), "one\nfixed\n")
        self.assertFalse((reviewer_1 / "two.txt").exists())
        self.assertEqual(out(reviewer_2, "rev-parse", "HEAD"), a2)
        self.assertEqual((reviewer_2 / "two.txt").read_text(encoding="utf-8"), "two\n")
        self.assertFalse((reviewer_2 / "one.txt").exists())
        # The round-7 shape, one key for the workflow overwritten by the fix,
        # would have sent item 2's reader to B1, where item 2's file does not exist.
        self.assertNotEqual(git(rig.rig, "cat-file", "-e", f"{b1}:two.txt", check=False).returncode, 0)
        # The key-absent fallback is per anchor too: item 2's own record, not item 1's.
        self.assertEqual(rig.reader_reads_current_commit(context, {}, item_2), a2)
        self.assertEqual(rig.reader_reads_current_commit(context, {}, item_1), b1)

        self.assertIsNone(rig.holder_of(item_1))
        self.assertIsNone(rig.holder_of(item_2))
        self.assert_no_contention()
        self.assert_rig_root_untouched()

    def test_relaunched_item_under_a_new_step_id_reuses_its_branch_and_keeps_its_commits(self) -> None:
        """Rule 10 (gate r9 MAJOR). Run 1: the operator lane is on the step
        branch `pre_start` cut for its step bead; no branch names the item, so
        prepare-worktree creates `<anchor>` from the base and records it; the
        step branch is left at the base, recorded nowhere. implement commits
        on the item's branch and releases. Re-launch: a NEW run, a NEW step
        id, so `pre_start` puts the SAME operator lane on a fresh step branch
        with none of the work. While the implement lane still holds the
        branch (a crash before its release) the re-launch fails closed naming
        the holder and records nothing; the same when a HUMAN checks the item
        branch out in the rig root (codex r1: checkout state must never turn
        a held item branch into a fresh one). Once free, the record names the
        item and exists: the lane switches onto it, records nothing, sits at
        the committed work, and the next implement lane continues ON TOP of
        the earlier commit. Round 9's shape recorded the fresh step branch
        here, whose tip is the base without the file."""
        rig = self.rig
        anchor: dict[str, str] = {}  # the source anchor's metadata: no record yet
        operator = rig.lane("run-operator", step="gp-step1")

        first = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(first, {"gc.outcome": "pass", "chosen_by": "new", "branch": ITEM_BRANCH, "recorded": True})
        self.assertEqual(anchor, {"gc.work_branch": ITEM_BRANCH})
        self.assertEqual(out(operator, "rev-parse", "gp-step1"), rig.main_sha)  # the step branch: unused, unrecorded
        implement = rig.lane("implementation-worker-1", step="gp-step2")
        rig.writer_takes(implement)
        impl_commit = commit(implement, "feature.txt", "implemented\n", "implement")

        # Re-launch while the writer still holds the branch: fail closed, nothing moves.
        rig.pre_start(operator, "gp-step5")
        refused = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual((refused["gc.outcome"], refused["failure"], refused["holder"]), ("fail", "held", str(implement)))
        self.assertRegex(str(refused["git"]), r"already (checked out|used by worktree) at")
        self.assertIn(implement.name, str(refused["reason"]))
        rig.stderr_seen.remove(refused["git"])
        self.assertEqual(anchor, {"gc.work_branch": ITEM_BRANCH})
        self.assertEqual(out(operator, "branch", "--show-current"), "gp-step5")
        self.assertEqual(rig.holder_of(ITEM_BRANCH), str(implement))
        rig.writer_releases(implement)

        # A human checks the item branch out in the rig root: the holder is the
        # rig root; the step fails closed, records nothing, forces nothing.
        git(rig.rig, "switch", "--quiet", ITEM_BRANCH)
        rig.pre_start(operator, "gp-step6")
        refused = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual((refused["gc.outcome"], refused["failure"], refused["holder"]), ("fail", "held", str(rig.rig)))
        rig.stderr_seen.remove(refused["git"])
        self.assertEqual(anchor, {"gc.work_branch": ITEM_BRANCH})
        self.assertEqual(out(rig.rig, "branch", "--show-current"), ITEM_BRANCH)
        self.assertEqual(out(rig.rig, "rev-parse", "HEAD"), impl_commit)
        git(rig.rig, "switch", "--quiet", "main")  # the human releases it
        self.assert_rig_root_untouched()

        # Free again, under yet another step id: the record names the item and exists.
        rig.pre_start(operator, "gp-step7")
        self.assertFalse((operator / "feature.txt").exists())  # the fresh cut knows nothing of the work
        second = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(second, {"gc.outcome": "pass", "chosen_by": "name", "branch": ITEM_BRANCH, "recorded": False})
        self.assertEqual(anchor, {"gc.work_branch": ITEM_BRANCH})  # unchanged
        self.assertEqual(out(operator, "branch", "--show-current"), "")  # released again
        self.assertEqual(out(operator, "rev-parse", "HEAD"), impl_commit)  # at the committed work
        self.assertEqual((operator / "feature.txt").read_text(encoding="utf-8"), "implemented\n")
        self.assertEqual(out(operator, "rev-parse", "gp-step7"), rig.main_sha)  # left at the base, recorded nowhere
        self.assertIsNone(rig.holder_of(ITEM_BRANCH))

        # A retry of this step after the record, before the detach: the lane is
        # on the branch already; taking it is a no-op, not a refusal.
        rig.writer_takes(operator)
        retried = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(retried, {"gc.outcome": "pass", "chosen_by": "name", "branch": ITEM_BRANCH, "recorded": False})

        # The re-launched implement lane (its own new step id) continues on top of the earlier commit.
        implement_2 = rig.lane("implementation-worker-2", step="gp-step8")
        rig.writer_takes(implement_2, anchor["gc.work_branch"])
        self.assertEqual((implement_2 / "feature.txt").read_text(encoding="utf-8"), "implemented\n")
        continued = commit(implement_2, "feature.txt", "implemented\nmore\n", "implement, continued")
        rig.writer_releases(implement_2)
        self.assertEqual(out(operator, "rev-parse", f"{continued}^"), impl_commit)
        self.assertEqual(rig.close_verifies(operator, anchor["gc.work_branch"]), continued)
        # Round 9 recorded the fresh step branch instead: its tip is the base, without the file.
        self.assertNotEqual(git(rig.rig, "cat-file", "-e", "gp-step7:feature.txt", check=False).returncode, 0)

        self.assert_no_contention()
        self.assert_rig_root_untouched()

    def test_relaunched_item_with_a_stale_record_finds_its_branch_by_name_or_starts_anew(self) -> None:
        """Rule 10, the record is not the operand. After run 1 the record can
        be wrong three ways, and the NAME rule resolves each: (A) a claim-time
        stamp overwrote the record with `main`: the one branch naming the item
        is found and the record re-aligned, the work present; (B) a human
        renamed the branch keeping the id (`wip/gp-item1-fix`): found by name,
        recorded, the work present; (C) renamed without the id: nothing names
        the item, so a new `<anchor>` starts from the base and is recorded,
        the renamed branch and its commit untouched; (D) two branches name
        the item: the step fails closed listing both and records nothing, as
        `pre_start` does."""
        rig = self.rig
        anchor: dict[str, str] = {}
        operator = rig.lane("run-operator", step="gp-step1")
        rig.operator_resolves_branch(operator, anchor)
        implement = rig.lane("implementation-worker-1", step="gp-step2")
        rig.writer_takes(implement)
        impl_commit = commit(implement, "feature.txt", "implemented\n", "implement")
        rig.writer_releases(implement)

        # (A) a claim-time stamp between runs.
        anchor["gc.work_branch"] = "main"
        rig.pre_start(operator, "gp-step7")
        result = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(result, {"gc.outcome": "pass", "chosen_by": "name", "branch": ITEM_BRANCH, "recorded": True})
        self.assertEqual(anchor, {"gc.work_branch": ITEM_BRANCH})
        self.assertEqual(out(operator, "rev-parse", "HEAD"), impl_commit)
        self.assertEqual(out(rig.rig, "rev-parse", "main"), rig.main_sha)  # nothing landed on main

        # (B) renamed, id kept.
        rig.run(operator, "branch", "-m", ITEM_BRANCH, "wip/gp-item1-fix")
        rig.pre_start(operator, "gp-step8")
        result = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(result, {"gc.outcome": "pass", "chosen_by": "name", "branch": "wip/gp-item1-fix", "recorded": True})
        self.assertEqual(anchor, {"gc.work_branch": "wip/gp-item1-fix"})
        self.assertEqual(out(operator, "rev-parse", "HEAD"), impl_commit)

        # (B2, codex r2) a LOCAL branch literally named `origin/<id>`: listed
        # per namespace, its name is kept, so it is found and taken as is
        # rather than a fresh `<id>` being created beside it.
        rig.run(operator, "branch", "-m", "wip/gp-item1-fix", "origin/gp-item1")
        rig.pre_start(operator, "gp-step8b")
        result = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(result, {"gc.outcome": "pass", "chosen_by": "name", "branch": "origin/gp-item1", "recorded": True})
        self.assertEqual(anchor, {"gc.work_branch": "origin/gp-item1"})
        self.assertEqual(out(operator, "rev-parse", "HEAD"), impl_commit)
        self.assertNotEqual(git(operator, "rev-parse", "--verify", "--quiet", "refs/heads/gp-item1", check=False).returncode, 0)
        rig.run(operator, "branch", "-m", "origin/gp-item1", "wip/gp-item1-fix")

        # (C) renamed, id dropped: the work is not the item's any more; start anew.
        rig.run(operator, "branch", "-m", "wip/gp-item1-fix", "kept/other")
        rig.pre_start(operator, "gp-step9")
        result = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(result, {"gc.outcome": "pass", "chosen_by": "new", "branch": ITEM_BRANCH, "recorded": True})
        self.assertEqual(anchor, {"gc.work_branch": ITEM_BRANCH})
        self.assertEqual(out(operator, "rev-parse", "--verify", f"refs/heads/{ITEM_BRANCH}"), rig.main_sha)
        self.assertEqual(out(operator, "rev-parse", "kept/other"), impl_commit)  # untouched
        implement_2 = rig.lane("implementation-worker-2", step="gp-step10")
        rig.writer_takes(implement_2, anchor["gc.work_branch"])
        self.assertFalse((implement_2 / "feature.txt").exists())
        rig.writer_releases(implement_2)

        # (D) several branches name the item: fail closed, list them, record nothing.
        rig.run(operator, "branch", "gp-item1-alt", rig.main_sha)
        anchor["gc.work_branch"] = "main"  # a stale record again, so the name rule must choose
        rig.pre_start(operator, "gp-step11")
        result = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(result, {"gc.outcome": "fail", "failure": "several", "candidates": [ITEM_BRANCH, "gp-item1-alt"]})
        self.assertEqual(anchor, {"gc.work_branch": "main"})
        self.assertEqual(out(operator, "branch", "--show-current"), "gp-step11")

        # (E, codex r2) several, and the record is one of them: a stamp of a
        # human branch that happens to contain the id (`human/gp-item1-notes`)
        # must not shortcut the enumeration onto the human's branch while the
        # work sits on `gp-item1`. Still fail closed, still nothing recorded.
        rig.run(operator, "branch", "-m", "gp-item1-alt", "human/gp-item1-notes")
        anchor["gc.work_branch"] = "human/gp-item1-notes"
        rig.pre_start(operator, "gp-step12")
        result = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(result, {"gc.outcome": "fail", "failure": "several", "candidates": [ITEM_BRANCH, "human/gp-item1-notes"]})
        self.assertEqual(anchor, {"gc.work_branch": "human/gp-item1-notes"})
        self.assertEqual(out(operator, "branch", "--show-current"), "gp-step12")
        # The operator reconciles: the human's branch loses the id; the next run finds one.
        rig.run(operator, "branch", "-m", "human/gp-item1-notes", "human/notes")
        rig.pre_start(operator, "gp-step13")
        result = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(result, {"gc.outcome": "pass", "chosen_by": "name", "branch": ITEM_BRANCH, "recorded": True})
        self.assertEqual(anchor, {"gc.work_branch": ITEM_BRANCH})
        self.assert_no_contention()
        self.assert_rig_root_untouched()

    def test_item_branch_only_on_origin_is_tracked_and_an_ignored_file_refusal_names_no_holder(self) -> None:
        """Rule 10, the two takes codex r2 asked to see run. Remote-only: the
        item's branch was pushed and the local name is gone; the enumeration
        finds it under `origin/` (prefix stripped from the remote namespace
        only), the lane takes it with `switch -c --track
        refs/remotes/origin/<branch>` (codex r5: a tag named
        `origin/<branch>` at the base makes the bare start point ambiguous
        and git refuse; the full ref is the branch), the work is present and
        the record is the unprefixed local name. An
        ignored file in the operator lane that the branch tracks makes git
        refuse; the step fails closed quoting git and naming NO holder (there
        is none), records nothing, and the lane and the file are as they were."""
        rig = self.rig
        anchor: dict[str, str] = {}
        operator = rig.lane("run-operator", step="gp-step1")
        rig.operator_resolves_branch(operator, anchor)
        implement = rig.lane("implementation-worker-1", step="gp-step2")
        rig.writer_takes(implement)
        impl_commit = commit(implement, "build.out", "tracked\n", "implement tracks a build output")
        rig.writer_releases(implement)

        origin = rig.root / "origin.git"
        subprocess.run(["git", "init", "--quiet", "--bare", str(origin)], check=True)
        git(rig.rig, "remote", "add", "origin", str(origin))
        git(rig.rig, "push", "--quiet", "origin", ITEM_BRANCH)
        rig.run(operator, "branch", "-m", ITEM_BRANCH, "kept/other")  # the local name is gone; origin still has it
        self.assertEqual(rig.branch_exists(operator, ITEM_BRANCH), "remote")
        git(rig.rig, "tag", f"origin/{ITEM_BRANCH}", rig.main_sha)  # a tag named like the remote-tracking ref, at the base
        # The hazard (codex r5): the bare start point is ambiguous, git refuses.
        hazard = rig.lane("run-operator-3", step="gp-step9")
        bare = git(hazard, "switch", "--no-overwrite-ignore", "-c", "hazard-take", "--track", f"origin/{ITEM_BRANCH}", check=False)
        self.assertNotEqual(bare.returncode, 0)
        self.assertIn("ambiguous", bare.stderr)
        self.assertEqual(out(hazard, "branch", "--show-current"), "gp-step9")
        self.assertEqual(git(hazard, "rev-parse", f"origin/{ITEM_BRANCH}").stdout.strip(), rig.main_sha)  # the tag

        rig.pre_start(operator, "gp-step7")
        result = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(result, {"gc.outcome": "pass", "chosen_by": "name", "branch": ITEM_BRANCH, "recorded": False})
        self.assertEqual(anchor, {"gc.work_branch": ITEM_BRANCH})
        self.assertEqual(out(operator, "rev-parse", "HEAD"), impl_commit)
        self.assertEqual(out(operator, "rev-parse", "--symbolic-full-name", f"{ITEM_BRANCH}@{{upstream}}"), f"refs/remotes/origin/{ITEM_BRANCH}")
        self.assertEqual((operator / "build.out").read_text(encoding="utf-8"), "tracked\n")

        # The ignored-file refusal: a second operator lane has an ignored
        # `build.out` the item's branch tracks.
        operator_2 = rig.lane("run-operator-2", step="gp-step8")
        (operator_2 / "build.out").write_text("ignored local\n", encoding="utf-8")
        info_exclude = pathlib.Path(out(operator_2, "rev-parse", "--git-path", "info/exclude"))
        info_exclude.parent.mkdir(parents=True, exist_ok=True)
        info_exclude.write_text("build.out\n", encoding="utf-8")
        self.assertEqual(out(operator_2, "status", "--porcelain"), "")
        before = rig.snapshot(operator_2)
        result = rig.operator_resolves_branch(operator_2, anchor)
        self.assertEqual((result["gc.outcome"], result["failure"], result["holder"]), ("fail", "refused", None))
        self.assertIn("build.out", str(result["git"]))
        self.assertIn("build.out", str(result["reason"]))
        self.assertNotIn("held at", str(result["reason"]))
        self.assertEqual(anchor, {"gc.work_branch": ITEM_BRANCH})
        self.assertEqual(rig.snapshot(operator_2), before)
        self.assertEqual((operator_2 / "build.out").read_text(encoding="utf-8"), "ignored local\n")
        self.assertIsNone(rig.holder_of(ITEM_BRANCH))
        self.assert_rig_root_untouched()

    def test_claim_time_stamp_never_names_the_item_and_is_never_reused(self) -> None:
        """Rule 10, the stamp. Older gc builds, and any session started in the
        rig root, stamp the rig root's branch on the bead they claim; the
        human checkout then moves between branches, so no checkout state can
        tell such a stamp from an item branch (codex r1, both directions).
        The name rule needs none: `main` and `human-work` do not name the
        item, whichever the rig root is on, so each stamp is passed over, the
        item's own branch is used, and no commit ever lands on a human
        branch. git itself refuses the branch the rig root holds; the step
        never has to ask."""
        rig = self.rig
        operator = rig.lane("run-operator", step="gp-step1")

        refused = rig.run(operator, "switch", "--no-overwrite-ignore", "main", check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertRegex(refused.stderr, r"already (checked out|used by worktree) at")
        self.assertIn(rig.rig.name, refused.stderr)
        rig.stderr_seen.remove(refused.stderr)

        transitions = (
            ("main", "main"),          # the stamp names the branch the rig root is on
            ("human-work", "main"),    # the rig root moved on; the stamp is stale
            ("human-work", "human-work"),
            ("main", "human-work"),
        )
        git(rig.rig, "branch", "--quiet", "human-work", "main")
        for index, (stamp, rig_root_on) in enumerate(transitions):
            with self.subTest(stamp=stamp, rig_root_on=rig_root_on):
                git(rig.rig, "switch", "--quiet", rig_root_on)
                rig.pre_start(operator, f"gp-step{index + 2}")
                anchor = {"gc.work_branch": stamp}
                result = rig.operator_resolves_branch(operator, anchor)
                self.assertEqual(result["gc.outcome"], "pass")
                self.assertEqual(result["branch"], ITEM_BRANCH)
                self.assertEqual(result["chosen_by"], "new" if index == 0 else "name")
                self.assertEqual(anchor, {"gc.work_branch": ITEM_BRANCH})
                self.assertEqual(out(rig.rig, "rev-parse", "--verify", f"refs/heads/{stamp}"), rig.main_sha)  # nothing landed on it
                self.assertEqual(out(rig.rig, "branch", "--show-current"), rig_root_on)
        git(rig.rig, "switch", "--quiet", "main")
        self.assert_no_contention()
        self.assert_rig_root_untouched()

    def test_a_tag_of_the_same_name_does_not_change_the_branch_name(self) -> None:
        """Rule 10, codex r3: `%(refname:short)` prints `heads/gp-item1` once a
        tag `gp-item1` exists, and a listing built on it would probe a branch
        that does not exist and fall through to a fresh base branch. The
        listing uses full ref names with one namespace prefix removed, so the
        branch keeps its name, is found, and is taken with the work present."""
        rig = self.rig
        anchor: dict[str, str] = {}
        operator = rig.lane("run-operator", step="gp-step1")
        rig.operator_resolves_branch(operator, anchor)
        implement = rig.lane("implementation-worker-1", step="gp-step2")
        rig.writer_takes(implement)
        impl_commit = commit(implement, "feature.txt", "implemented\n", "implement")
        rig.writer_releases(implement)

        git(rig.rig, "tag", ITEM_BRANCH, rig.main_sha)  # a tag with the branch's name
        # The abbreviation git would print for the branch now carries a namespace.
        self.assertEqual(out(rig.rig, "for-each-ref", "--format=%(refname:short)", f"refs/heads/{ITEM_BRANCH}"), f"heads/{ITEM_BRANCH}")
        self.assertEqual(rig.item_branches(ITEM_BRANCH), [ITEM_BRANCH])

        rig.pre_start(operator, "gp-step7")
        result = rig.operator_resolves_branch(operator, anchor)
        self.assertEqual(result, {"gc.outcome": "pass", "chosen_by": "name", "branch": ITEM_BRANCH, "recorded": False})
        self.assertEqual(out(operator, "rev-parse", "HEAD"), impl_commit)
        self.assertEqual((operator / "feature.txt").read_text(encoding="utf-8"), "implemented\n")
        self.assertNotEqual(git(operator, "rev-parse", "--verify", "--quiet", f"refs/heads/heads/{ITEM_BRANCH}", check=False).returncode, 0)
        self.assert_no_contention()
        self.assert_rig_root_untouched()

    def test_a_tag_at_the_base_never_redirects_review_from_the_branch_tip(self) -> None:
        """Rule 11 (round 2, the mayor's codex gate r1 on fork #34). Round 1's
        listing keeps the branch's NAME beside a tag of the same name, but
        the consumers of `gc.work_branch` then resolved that name bare, and
        git resolves a bare name tag-first: with the tag at the base, the
        review setup would have recorded the base as the commit under review,
        every review lane would have inspected it, close-source-anchor would
        have verified it, and the fix lane's refresh would have re-recorded
        it. Every such read names `refs/heads/<branch>`; `git switch`
        resolves branches only and keeps the bare name. The hazard is shown
        first, on the same repository, then the lifecycle runs through
        review-commit recording with the tag in place."""
        rig = self.rig
        anchor: dict[str, str] = {}
        operator = rig.lane("run-operator", step="gp-step1")
        rig.operator_resolves_branch(operator, anchor)
        implement = rig.lane("implementation-worker-1", step="gp-step2")
        rig.writer_takes(implement)
        impl_commit = commit(implement, "feature.txt", "implemented\n", "implement")
        rig.writer_releases(implement)

        git(rig.rig, "tag", ITEM_BRANCH, rig.main_sha)  # a tag with the branch's name, at the base
        self.assertEqual(rig.item_branches(ITEM_BRANCH), [ITEM_BRANCH])  # round 1: the name survives

        # The hazard: a bare name is the TAG (git checks refs/tags before refs/heads) ...
        for bare in (
            ("rev-parse", ITEM_BRANCH),
            ("log", "-1", "--format=%H", ITEM_BRANCH),
            ("show", "-s", "--format=%H", ITEM_BRANCH),
        ):
            with self.subTest(bare=bare[0]):
                read = git(operator, *bare)
                self.assertEqual(read.stdout.strip(), rig.main_sha)
                self.assertIn("ambiguous", read.stderr)
        # ... the full ref is the branch, and `git switch` resolves branches only.
        self.assertEqual(out(operator, "rev-parse", "--verify", f"refs/heads/{ITEM_BRANCH}"), impl_commit)
        self.assertEqual(out(operator, "log", "-1", "--format=%H", f"refs/heads/{ITEM_BRANCH}"), impl_commit)
        self.assertEqual(out(operator, "show", "-s", "--format=%H", f"refs/heads/{ITEM_BRANCH}"), impl_commit)

        # close-source-anchor verifies the IMPLEMENTATION commit from its own lane.
        self.assertEqual(rig.close_verifies(operator), impl_commit)

        # setup-build-basic-review records the branch TIP as the commit under review.
        setup = rig.lane("run-operator-2", step="gp-step3")
        context, anchors = rig.setup_records(setup, [ITEM_BRANCH])
        self.assertEqual(anchors, {ITEM_BRANCH: {"gc.review_commit": impl_commit}})
        self.assertEqual(rig.context_commit(context, ITEM_BRANCH), impl_commit)
        self.assertNotIn(rig.main_sha, context.read_text(encoding="utf-8"))

        # A review lane detaches at the recorded commit and sees the implementation.
        reviewer = rig.lane("implementation-reviewer-1", step="gp-step4")
        current = rig.reader_reads_current_commit(context, anchors, ITEM_BRANCH)
        self.assertEqual(current, impl_commit)
        proc = rig.reader_detaches(reviewer, current)
        _, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out(reviewer, "rev-parse", "HEAD"), impl_commit)
        self.assertEqual((reviewer / "feature.txt").read_text(encoding="utf-8"), "implemented\n")

        # apply-review-findings: the bare `switch <branch>` lands on the BRANCH at
        # the implementation, the fix advances it, the refresh records the fixed tip.
        fix = rig.lane("implementation-worker-2", step="gp-step5")
        rig.writer_takes(fix)
        self.assertEqual(out(fix, "branch", "--show-current"), ITEM_BRANCH)
        self.assertEqual(out(fix, "rev-parse", "HEAD"), impl_commit)
        fix_commit = commit(fix, "feature.txt", "implemented\nfixed\n", "fix")
        refreshed = rig.fix_lane_refreshes(fix, context, anchors, ITEM_BRANCH)
        rig.writer_releases(fix)
        self.assertEqual(refreshed, fix_commit)
        self.assertEqual(anchors[ITEM_BRANCH]["gc.review_commit"], fix_commit)
        self.assertEqual(rig.context_commit(context, ITEM_BRANCH), fix_commit)
        self.assertEqual(rig.close_verifies(operator), fix_commit)
        # The tag never moved, and a bare read would still answer the base.
        self.assertEqual(out(operator, "rev-parse", f"refs/tags/{ITEM_BRANCH}"), rig.main_sha)
        self.assertEqual(git(operator, "rev-parse", ITEM_BRANCH).stdout.strip(), rig.main_sha)
        self.assertNotIn(rig.main_sha, context.read_text(encoding="utf-8"))

        self.assertIsNone(rig.holder_of(ITEM_BRANCH))
        self.assert_no_contention()
        self.assert_rig_root_untouched()

    def test_fix_in_a_per_item_worktree_refreshes_its_own_head_not_a_branch(self) -> None:
        """Rule 11, codex r5 finding 1. The refresh applies in the `work_dir`
        case too: the per-item worktree is detached at the fix commit and has
        no item branch to read, so the new commit id is `rev-parse --verify
        HEAD` of the worktree the fix was committed in. A branch named for
        the anchor at another commit and a tag of that name at the base
        change nothing, and there is no branch to release."""
        rig = self.rig
        anchor: dict[str, str] = {}
        operator = rig.lane("run-operator", step="gp-step1")
        rig.operator_resolves_branch(operator, anchor)
        implement = rig.lane("implementation-worker-1", step="gp-step2")
        rig.writer_takes(implement)
        impl_commit = commit(implement, "feature.txt", "implemented\n", "implement")
        rig.writer_releases(implement)
        setup = rig.lane("run-operator-2", step="gp-step3")
        context, anchors = rig.setup_records(setup, [ITEM_BRANCH])
        git(rig.rig, "tag", ITEM_BRANCH, rig.main_sha)

        # The work_dir case: a per-item worktree, detached at the recorded commit, shared with no one.
        item_worktree = rig.root / "worktrees" / ITEM_BRANCH
        git(rig.rig, "worktree", "add", "--quiet", "--detach", str(item_worktree), impl_commit)
        self.assertEqual(out(item_worktree, "branch", "--show-current"), "")
        fix_commit = commit(item_worktree, "feature.txt", "implemented\nfixed\n", "fix in the per-item worktree")
        refreshed = rig.fix_lane_refreshes(item_worktree, context, anchors, ITEM_BRANCH)
        self.assertEqual(refreshed, fix_commit)
        self.assertEqual(anchors[ITEM_BRANCH]["gc.review_commit"], fix_commit)
        self.assertEqual(rig.context_commit(context, ITEM_BRANCH), fix_commit)
        # Neither the branch (still at the implementation) nor the tag (the base) was read.
        self.assertEqual(out(rig.rig, "rev-parse", "--verify", f"refs/heads/{ITEM_BRANCH}"), impl_commit)
        self.assertEqual(out(rig.rig, "rev-parse", f"refs/tags/{ITEM_BRANCH}"), rig.main_sha)
        self.assertNotIn(impl_commit, context.read_text(encoding="utf-8"))
        self.assertEqual(out(item_worktree, "branch", "--show-current"), "")  # nothing to release
        self.assertIsNone(rig.holder_of(ITEM_BRANCH))
        self.assert_no_contention()
        self.assert_rig_root_untouched()

    def test_claim_without_a_trigger_bead_takes_the_beads_existing_branch(self) -> None:
        """Rule 10, codex r3, the role fragment's no-trigger case. A pooled
        worker's `pre_start` had no trigger bead and left the lane detached at
        the base; the worker then claims a bead whose committed work is on
        `fix/<id>-x`. The fragment has it take that branch by the same name
        rule (never create `<id>` beside it): the lane switches onto it, the
        work is present, the record is re-aligned to that name, and exactly
        one branch names the bead afterwards. With no branch naming the bead
        it creates `<id>`."""
        rig = self.rig
        bead = "gp-item1"
        pooled = rig.lane("implementation-worker-1", detached=True)
        self.assertEqual(out(pooled, "branch", "--show-current"), "")
        self.assertEqual(out(pooled, "rev-parse", "HEAD"), rig.main_sha)
        # The bead's earlier work, on a branch a human named for it.
        earlier = rig.lane("implementation-worker-0", step="fix/gp-item1-x")
        work = commit(earlier, "feature.txt", "implemented\n", "implement")
        rig.writer_releases(earlier)

        anchor = {"gc.work_branch": "main"}  # the claim-time stamp
        result = rig.operator_resolves_branch(pooled, anchor, anchor=bead, keep=True)
        self.assertEqual(result, {"gc.outcome": "pass", "chosen_by": "name", "branch": "fix/gp-item1-x", "recorded": True})
        self.assertEqual(anchor, {"gc.work_branch": "fix/gp-item1-x"})
        # The claiming worker is the writer: it holds the branch, and its commit advances it.
        self.assertEqual(out(pooled, "branch", "--show-current"), "fix/gp-item1-x")
        self.assertEqual(rig.holder_of("fix/gp-item1-x"), str(pooled))
        self.assertEqual(out(pooled, "rev-parse", "HEAD"), work)
        self.assertEqual((pooled / "feature.txt").read_text(encoding="utf-8"), "implemented\n")
        more = commit(pooled, "feature.txt", "implemented\nmore\n", "continue on the bead's branch")
        self.assertEqual(out(rig.rig, "rev-parse", "--verify", "refs/heads/fix/gp-item1-x"), more)
        self.assertEqual(out(rig.rig, "rev-parse", f"{more}^"), work)
        self.assertEqual(rig.item_branches(bead), ["fix/gp-item1-x"])  # still exactly one
        self.assertNotEqual(git(pooled, "rev-parse", "--verify", "--quiet", "refs/heads/gp-item1", check=False).returncode, 0)
        rig.writer_releases(pooled)

        # A bead with no branch at all, claimed by another pooled lane detached
        # at the base: it creates `<id>` from the base and records it.
        pooled_2 = rig.lane("implementation-worker-2", detached=True)
        fresh = {"gc.work_branch": ""}
        result = rig.operator_resolves_branch(pooled_2, fresh, anchor="gp-item2", keep=True)
        self.assertEqual(result, {"gc.outcome": "pass", "chosen_by": "new", "branch": "gp-item2", "recorded": True})
        self.assertEqual(fresh, {"gc.work_branch": "gp-item2"})
        self.assertEqual(out(pooled_2, "branch", "--show-current"), "gp-item2")
        self.assertEqual(out(pooled_2, "rev-parse", "HEAD"), rig.main_sha)
        self.assertFalse((pooled_2 / "feature.txt").exists())
        self.assert_no_contention()
        self.assert_rig_root_untouched()


if __name__ == "__main__":
    unittest.main()
