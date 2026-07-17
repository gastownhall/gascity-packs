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
- Read the canonical plan at workflow root metadata `gc.build.plan_path`
  (fallback `gc.var.plan_path`) and require its top-level front-matter value to
  be `status: approved`. Plan-review approval metadata is not sufficient when
  the artifact remains draft.
- From the launcher rig root, run the terminal's canonical artifact check with
  `GC_BEAD_ID="$CLAIMED_BEAD_ID" .gc/scripts/checks/build-artifact-valid.sh`.
  Repair only the canonical plan and rerun until the check passes.
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
