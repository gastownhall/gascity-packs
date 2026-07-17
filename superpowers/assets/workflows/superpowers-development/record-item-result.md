Record the Superpowers task result.

Update the per-item summary with changed files, test commands, command output
locations, commits to make, blockers, and traceability back to the plan task.
If the task could not be completed, record the blocker and leave the source
anchor open with a failing outcome instead of hiding the failure.

Before recording changed files or scope compliance, run `git status --short`
and `git diff --name-only HEAD` in the task worktree. Reconcile every reported
tracked, staged, and untracked path with the approved task scope. Never claim
that a file was unchanged when Git reports it as modified. If a changed path
violates an approved non-goal, revert that path or record a blocker; do not
record a passing result.

Create a focused commit for this task when the verification evidence is clean
and the repository state is ready. Use the approved plan's commit guidance when
it gives an exact message; otherwise use a concise message scoped to the task.

Before recording success, resolve the exact source anchor again and read its
absolute `work_dir` as `WORKTREE`. The per-item implementation summary must be
at the current absolute `gc.implementation.summary_path` inside that worktree;
do not use a launcher or attempt-local artifact as the member summary. From the
same worktree, read the focused commit with `git rev-parse HEAD`.

Persist the proof tuple on the source anchor bead itself in one update:

```bash
gc bd update <source-anchor-id> \
  --set-metadata "gc.implementation.worktree_path=$WORKTREE" \
  --set-metadata "gc.implementation.commit=<full-HEAD-from-WORKTREE>" \
  --set-metadata "gc.implementation.summary_path=<absolute-summary-inside-WORKTREE>"
```

Read the source anchor bead back. Require `work_dir` and
`gc.implementation.worktree_path` to resolve to the same worktree, the recorded
commit to equal that worktree's `HEAD`, and the recorded summary to exist
inside that worktree before the later close-source-anchor step may close it.

Do not invoke provider-native subagents or upstream plugin runtime commands.
