
Resolve `<source-anchor-id>` using the same rules as `prepare-worktree`. Read `work_dir` from the source anchor and verify the implementation commit and
summary evidence are present in that worktree. Write per-item summary to
{{summary_path}} when set. If `summary_path` is not set, first use
`gc.implementation.summary_path` from the preceding implementation step when it
is present; otherwise use `{{artifact_root}}/task-<source-anchor-id>-summary.md`.

When reading beads with `gc bd show --json`, handle both an object and a
one-element list before reading metadata. `gc.work_dir` is the launcher rig
root, not the implementation worktree. Unless the lane case below applies, if the source anchor `work_dir` is
missing, equals the launcher root, or points at a worktree without the
implementation commit, fail this step instead of closing the source anchor.

When the source anchor has no `work_dir` and records `gc.work_branch`
(`prepare-worktree` ran in a lane and handed the item over by branch), verify
from your own lane instead: `git -C "$GC_DIR" log -1 <gc.work_branch>` shows
the implementation commit (every worktree of the rig shares its refs) and the
summary exists at the recorded summary path. Never enter another agent's lane
to verify, and fail this step if the branch is missing from the repository. A
persisted `work_dir` that names an agent lane (`.worktrees/<rig>/lane-*`) is
invalid, whoever's it is: fail this step instead of entering it.

On success, close only `<source-anchor-id>` with `gc.outcome=pass`. Include the
verified commit and summary path in the source-anchor close reason. Read the
source anchor back with `gc bd show <source-anchor-id> --json` and verify
`status=closed` and `gc.outcome=pass`; if either check fails, fix the source
anchor before closing this step. Do not close this step with pass while the source anchor remains open. Then close this step. Do not close the drain-unit
convoy, parent convoy, or broader workflow root from this step.
