Write a gstack report-only review for `{{subject_path}}` and save it to
`{{report_path}}`.

Use the gstack review posture: staff-engineer correctness, QA evidence,
security concerns, and completeness gaps. Because this entry point is
report-only, do not apply fixes unless the parent workflow explicitly routes a
fix lane.

Do not invoke provider-native subagents. Gas City fanouts own review
delegation.

Artifact validation: this step is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the report recorded at `gc.build.review_report_path` (fallback `gc.var.report_path`) against schema `gc.build.review.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the report in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the report.
