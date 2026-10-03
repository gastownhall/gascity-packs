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
5. close-source-anchor reads `git log -1 <branch>`.

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

Every step below runs the exact git commands the formula text names, in real
worktrees under a temporary directory, with no network. The static rows in
test_formula_assets pin the sentences; this file pins that the sentences work.
"""

from __future__ import annotations

import pathlib
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

    def lane(self, role: str) -> pathlib.Path:
        path = self.lanes_root / f"lane-gc.{role}"
        path.parent.mkdir(parents=True, exist_ok=True)
        # pre_start puts the lane on the STEP bead's branch, cut from HEAD.
        git(self.rig, "worktree", "add", "--quiet", "-b", f"step-{role}", str(path), "main")
        return path

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

    # --- round 7: the recorded commit and the boundary test ------------------

    REVIEW_COMMIT_KEY = "gc.review_commit"

    def setup_records(self, lane: pathlib.Path, anchors: list[str]) -> tuple[pathlib.Path, dict[str, dict[str, str]]]:
        """setup-build-basic-review, from ITS OWN lane: one record PER SOURCE
        ANCHOR in the review context file (the anchor id, its branch, the
        branch's commit, the changed files), and `gc.review_commit` on EACH
        source anchor (the anchors' metadata modelled as a dict per anchor id:
        the bead store is not part of this test). Nothing is recorded on the
        workflow root. The branch is named for the source anchor."""
        context = self.root / "artifacts" / "code-review-context.md"
        context.parent.mkdir(parents=True, exist_ok=True)
        records = []
        anchor_metadata: dict[str, dict[str, str]] = {}
        for anchor in anchors:
            commit_id = out(lane, "rev-parse", anchor)
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
        Every other anchor's record and key are left untouched."""
        new_commit = out(lane, "rev-parse", "HEAD")
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
        recorded = out(reviewer_a, "rev-parse", ITEM_BRANCH)
        self.assertEqual(recorded, impl_commit)
        self.assertEqual(out(reviewer_a, "log", "-1", "--format=%H", ITEM_BRANCH), impl_commit)

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
        self.assertEqual(out(operator, "log", "-1", "--format=%H", ITEM_BRANCH), fix_commit)
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
        self.assertEqual(out(operator, "log", "-1", "--format=%H", ITEM_BRANCH), fix_commit)
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
        self.assertEqual(out(operator, "log", "-1", "--format=%H", ITEM_BRANCH), commit_b)

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
        recorded = out(implement, "rev-parse", ITEM_BRANCH)
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
        self.assertEqual(out(operator, "log", "-1", "--format=%H", item_1), b1)
        self.assertEqual(out(operator, "log", "-1", "--format=%H", item_2), a2)

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


if __name__ == "__main__":
    unittest.main()
