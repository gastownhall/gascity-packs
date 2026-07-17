
Resolve `<source-anchor-id>` using the same rules as `prepare-worktree`.
Read `work_dir` from the source anchor. Read the source anchor bead back and
require its absolute `work_dir`,
`gc.implementation.worktree_path`, `gc.implementation.commit`, and
`gc.implementation.summary_path`. Require both worktree paths to name the same
worktree, the recorded commit to equal that worktree's `HEAD`, and the summary
to exist inside that worktree. Never choose a commit with `git log --all`, from
a sibling worktree, or from repository-wide history. If any proof is missing
or mismatched, leave the source anchor open and fail this step.

On success, close only `<source-anchor-id>` with `gc.outcome=pass`. Include the
verified commit and summary path in the source-anchor close reason. Read the
source anchor back with `gc bd show <source-anchor-id> --json` and verify
`status=closed` and `gc.outcome=pass`; if either check fails, fix the source
anchor before closing this step. Do not close this step with pass while the source anchor remains open. Then close this step. Do not close the drain-unit
convoy, parent convoy, or broader workflow root from this step.
