Use the assigned Compound Engineering final synthesis skill. Finalization lane
delegation is defined by the formula graph; this stage records artifact
inventory, review-resolution verification, any deployment notes preserved by
code review, and final synthesis.

Do not invoke provider-native subagents or upstream plugin runtime commands.

Artifact validation: this stage is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.final_report_path` against schema `gc.build.final-report.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
