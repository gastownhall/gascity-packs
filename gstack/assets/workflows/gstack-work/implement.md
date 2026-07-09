Implement the assigned gstack work bead.

Gas City owns the worktree, bead, and convoy plumbing. Read the assigned
implementation bead, the approved plan, and any context bundle before editing.
Use the gstack discipline: ship the narrowest complete slice, test it, review
your own diff, and record proof.

Your summary must include intended behavior, first verification command,
changed files, proof command, remaining risks, and any release consideration.

Close with `gc.outcome=pass` only after the work is implemented and verified.

Do not invoke provider-native subagents. You are the implementation lane.

Artifact validation: this step is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
