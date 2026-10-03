Implement the assigned gstack work bead.

Gas City owns the worktree, bead, and convoy plumbing. Read the assigned
implementation bead, the approved plan, and any context bundle before editing.
Use the gstack discipline: ship the narrowest complete slice, test it, review
your own diff, and record proof.

Resolve the source anchor with the same rules as the inherited
`prepare-worktree` step, read `work_dir` from the source anchor, validate that
it is an absolute existing git worktree, set `WORKTREE` to that path, and
`cd "$WORKTREE"` before reading or editing source files. If `work_dir` is
missing, invalid, or points at the launcher checkout, fail before editing.
`gc.work_dir` is the launcher rig root, not the implementation worktree; do not
edit, test, or commit in the launcher checkout.

Implement only the owned source anchor boundary, run focused verification from
inside the worktree, then make a focused commit in the worktree (`git add` the
changed files and `git commit`). The inherited `close-source-anchor` step fails
closed when the worktree has no implementation commit, so uncommitted edits are
a failed implementation, not a pass. Record the summary path, focused commit
hash, changed files, and verification result on this implement step and on the
source anchor before closing this step. Leave the source anchor open for the
`close-source-anchor` step.

Your summary must include intended behavior, first verification command,
changed files, the focused commit hash, proof command, remaining risks, and any
release consideration.

Close with `gc.outcome=pass` only after the work is implemented, verified, and
committed.

Do not invoke provider-native subagents. You are the implementation lane.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
