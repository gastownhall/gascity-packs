Finalize the Superpowers plan-review expansion.

Verify the latest loop verdict from the plan-review wrapper and the
apply-plan-feedback lane.

Approval path:

- Confirm `design_review.review_verdict=approve` on the plan-document-review
  lane.
- Confirm `design_review.verdict=done` on the apply-plan-feedback lane.
- Confirm the report exists at workflow root metadata
  `gc.build.plan_review_report_path`.
- Confirm the apply summary exists at workflow root metadata
  `gc.build.plan_review_apply_summary_path`.
- Update workflow root metadata:
  - `gc.build.plan_review_status=approved`
  - `gc.build.plan_status=approved`
  - `gc.build.plan_review_approved_at=<UTC timestamp>`
- Close this expansion target with `gc.outcome=pass`,
  `design_review.review_verdict=approve`,
  `design_review.verdict=done`, and
  `design_review.output_path=<plan review report path>`.

Failure path:

- If unresolved required findings remain, do not approve the expansion.
- Update workflow root metadata with `gc.build.plan_review_status=failed`.
- Close with `gc.outcome=fail`, `design_review.output_path=<report path>`,
  and a concise `gc.failure_reason` that points at the blocking finding.

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
  `changes_required`, `blocked`, or `superseded`; replace any other value
  (for example `reviewed`) with the allowed status that matches the review
  outcome (`approved` for an approved plan).
- On repair attempts (`gc.attempt` greater than 1), first read the validator
  errors from `gc.attempt_log` on the validation loop control bead (the
  dependent of this step bead) and fix every listed error in place.
