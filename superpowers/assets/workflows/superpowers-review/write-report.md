Run Superpowers code review for `{{subject_path}}` with optional context
`{{context_path}}`. Write the final adapter-consumable report to
`{{report_path}}`; do not post comments, push branches, or finalize external
state here.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the report recorded at `gc.build.code_review_report_path` (fallback `gc.build.review_report_path`, then `gc.var.report_path`) against schema `gc.build.review.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the report in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the report.
