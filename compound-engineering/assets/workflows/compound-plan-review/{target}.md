Finalize the Compound Engineering plan-review expansion.

Verify the latest synthesized verdict is approved, record the review report path on the parent build step, and close this expansion target. If the loop exhausted attempts or has unresolved required findings, record a failing review outcome with the report path.

Use workflow root metadata `gc.build.plan_review_report_path` and
`gc.build.plan_review_apply_summary_path`. On success, update the workflow root
with `gc.build.plan_review_status=approved` and
`gc.build.plan_review_approved_at=<UTC timestamp>`, then close with
`gc.outcome=pass`.

Plan artifact validation: this step is gated by
`.gc/scripts/checks/build-artifact-valid.sh`, which validates the plan
recorded at workflow root metadata `gc.build.plan_path` (fallback
`gc.var.plan_path`) against schema `gc.build.plan.v1`. Plan-review fix lanes
edit the plan in place, so re-validate it here before closing:

- From `$GC_RIG_ROOT`, run the artifact validator with the claimed bead id and
  fix any error before setting `gc.outcome=pass`:
  `GC_BEAD_ID=<claimed-step-id> .gc/scripts/checks/build-artifact-valid.sh`.
- Repair the plan in place and keep its YAML front matter intact. Its
  front-matter `status` must be one of `draft`, `questions`, `approved`,
  `changes_required`, `blocked`, or `superseded`. Replace any other value
  (for example `reviewed`) with the allowed status that matches the review
  outcome (`approved` for an approved plan).
- On repair attempts (`gc.attempt` greater than 1), first read the validator
  errors from `gc.attempt_log` on the validation loop control bead (the
  dependent of this step bead) and fix every listed error in place.
