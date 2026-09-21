This is the `fix-loop-base` methodology contract re-review step.

Concrete methodology packs override this step to call `{{code_review_formula}}`
after fixes. Continue only while the iteration count is below
`{{max_iterations}}`. Record the follow-up review report path on workflow root
metadata as `gc.build.review_report_path` before closing. Also record
`gc.build.review_verdict`, `gc.build.review_report_sha256`,
`gc.build.review_initial_findings`, and a `trace.upstream` entry
`{path: <worktree>, hash: git:<HEAD>, role: review-subject}` so the caller can
prove the re-review is fresh.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the report recorded at `gc.build.review_report_path` against schema `gc.build.review.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the report in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the report.
