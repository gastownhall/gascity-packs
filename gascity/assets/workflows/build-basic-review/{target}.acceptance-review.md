Run the starter factory acceptance review lane.

Review the implementation against the requirements, acceptance criteria,
implementation plan, decomposition, and task summaries. Focus on correctness:
did the factory build the requested behavior, and did it avoid out-of-scope
changes?

Read the review context first and evaluate the implementation source
anchor/worktree recorded there. The launcher rig root is not the review target
for build-basic; it may still contain the original fixture until publish. Do not
mark acceptance as `iterate` merely because the root checkout is unchanged when
the recorded source anchor/worktree implements the requested behavior and its
proof commands pass.

Before inspecting files or running tests, read `gc.build.code_review_context_path`
from the workflow root bead and use its `## Implementation Worktrees` section as
the authority for code under review. `gc.work_dir` is the launcher rig root, not
the implementation worktree. Do not inspect or edit the launcher checkout when
deciding whether the implementation passes. Resolve every relative source path
and proof command from the review context against the listed implementation
worktree, run `cd "$WORKTREE"`, and verify `pwd -P` equals that worktree before
executing commands. If the context is missing a usable implementation worktree,
write an iterate finding against review setup instead of reviewing the launcher
checkout.

Contract: `gc.work_dir` is the launcher rig root, not the implementation worktree.

The `## Implementation Worktrees` section carries one record per source
anchor, and each names the workspace either as that source anchor's `work_dir`
or, when the source anchor has no `work_dir` and records `gc.work_branch`, as
a branch and a commit id. Read the CURRENT commit first, per source anchor:
`gc.review_commit` on that source anchor bead (`gc bd show <source-anchor-id>
--json`, the id from its record in the context), which the review setup writes
on its first run and the fix lane refreshes after every fix commit on that
item; fall back to the commit in that anchor's record in the review context
file only when that key is absent. There is no workflow-wide review commit:
separate drains put several items on independent branches, and each is
inspected at its own commit. The review loop re-runs this lane after a fix,
and a commit read from a stale context re-reviews code that was already fixed
and repeats resolved findings. In the branch case work from
your OWN lane and never enter another agent's directory: read with `git -C
"$GC_DIR" log -1 <commit>` and `git -C "$GC_DIR" show <commit>:<path>` (every
worktree of the rig shares its refs, and both commands are safe from any
checkout of the rig's repository, the rig root included). To run proof
commands, inspect the recorded commit DETACHED in your own lane, and prove
the lane FIRST, before any `switch` or detach, with the boundary test
`do-work/prepare-worktree` step 4 applies (every path resolved through
symlinks, `pwd -P`): `git -C "$GC_DIR" rev-parse --show-toplevel` equals
`$GC_DIR` itself; that top-level is neither the rig root (`gc.work_dir` on
the workflow root bead) nor inside it; `git -C "$GC_DIR" rev-parse
--git-common-dir` is the rig root's `.git`. A reviewer role with no configured
`work_dir` starts in the RIG ROOT, the human checkout, and `$GC_DIR` then IS
the rig root: when any part fails, switch and detach NOTHING in `$GC_DIR` (a
detach run there moves the human checkout's HEAD), inspect by `git -C
"$GC_DIR" show <commit>:<path>` and `git -C "$GC_DIR" log -1 <commit>` only,
and if a proof command needs a checkout at the commit, close this lane with
`gc.outcome=fail`, `gc.failure_class=no-lane` and the reason "no lane for
this role", naming the fix: a `work_dir` for this role (README, Worker
workspaces). Only when all three parts hold: `git -C "$GC_DIR" switch --detach
--no-overwrite-ignore <commit>` (the current commit as read above; if
the context carries only the branch, resolve it first with `git -C "$GC_DIR"
rev-parse --verify "refs/heads/<gc.work_branch>"`, the full ref, since a bare
name resolves tag-first), and fail closed when git refuses (an ignored
file in your lane colliding with a tracked path, or a commit missing from the
repository): never `--force`, never a stash, never remove the colliding file.
A review lane never takes the branch itself: git allows one worktree per
branch, only the writers (implement, then the fix lane) hold it, one at a
time, and three reviewers detached at the same commit never contend and never
block the fix lane. A `work_dir` naming an agent lane
(`.worktrees/<rig>/lane-*`) is invalid: write an iterate finding against
review setup instead of entering it.

Write findings under the build artifact root. Required findings must include
the relevant requirement or task reference plus the file, command, or artifact
that proves the issue.

Close with `gc.outcome=pass`,
`code_review.acceptance_verdict=approve|iterate`, and
`code_review.output_path=<acceptance review report path>`.

Use explicit close metadata so the review loop can detect the lane result:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.acceptance_verdict=approve' \
  --set-metadata 'code_review.output_path=<acceptance review report path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Build-basic acceptance review approved.'
```

If you find required fixes, set
`code_review.acceptance_verdict=iterate` instead of `approve` and explain the
smallest required fix in the report and close reason.

Do not set `code_review.verdict` or `code_review.report_path`; synthesis and
fix application own the final review verdict.

Do not invoke provider-native subagents. You are the starter factory acceptance
review lane.
