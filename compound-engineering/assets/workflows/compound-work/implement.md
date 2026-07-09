Implement this Compound Engineering item with {{implementation_target}}.

Read `work_dir` from the source anchor, validate that it is an absolute existing
git worktree, set `WORKTREE` to that path, and `cd "$WORKTREE"` before reading
or editing source files. If `work_dir` is missing, invalid, or points at the
launcher checkout, fail before editing.

Use the installed ce-work guidance as the implementation prompt for this Gas
City lane. Implement only the owned source anchor boundary, run focused
verification from inside the worktree, and write an implementation summary.
After resolving the source anchor, write that summary to
`{{artifact_root}}/task-<source-anchor-id>-summary.md`. Record the summary path,
focused commit hash, changed files, and verification result on this implement
step and on the source anchor before closing this step.

Do not invoke provider-native subagents. Leave the source anchor open for the
close-source-anchor step.

Artifact validation: this step is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
