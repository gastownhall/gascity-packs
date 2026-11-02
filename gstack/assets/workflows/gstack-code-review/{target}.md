Finalize the gstack code review.

If workflow root metadata `gc.var.review_mode=report`, do not require the
apply-review-findings lane and do not apply fixes. Confirm the synthesized
review report exists at workflow root metadata `gc.build.code_review_report_path`.
Preserve the report's own verdict (`approved`, `changes_required`, or
`blocked`). In report mode, producing the validated report is the successful
deliverable even when findings require changes. Record
`gc.build.code_review_status=reported` on the workflow root, publish the
review report as described below, and close with
`gc.outcome=pass`, `code_review.verdict=reported`, and
`code_review.report_path=<synthesized report path>`.

Verify the latest review loop approved the implementation: confirm
`code_review.verdict=done` on the apply-review-findings lane, the synthesized
review report at workflow root `gc.build.code_review_report_path`, and the
review-fix summary at `gc.build.review_fix_summary_path`. Record
`gc.build.code_review_status=approved` and
`gc.build.code_review_approved_at=<UTC timestamp>` on the workflow root for QA
and the final sprint report.

On both passing paths (report mode and approval), publish the synthesized report
as the stage review report before closing. The terminal artifact check on this
step and the build gate validate the file recorded at workflow root metadata
`gc.build.review_report_path` against `gc.build.review.v1`. The build prepare
stage pre-declares that key as `<artifact_root>/review-report.md`, which this
expansion does not otherwise write:

- Resolve the review report path: use workflow root metadata
  `gc.build.review_report_path` when it is set; otherwise use the synthesized report
  path from `gc.build.code_review_report_path`.
- If the resolved review report path is relative, resolve it against
  `$GC_RIG_ROOT` before copying and recording it.
- If the review report path differs from the synthesized report path, copy the
  synthesized report to it with `mkdir -p "$(dirname "<review report path>")"`
  and `cp -f "<synthesized report path>" "<review report path>"`.
- Record the absolute review report path on the workflow root bead, not on the
  claimed step bead:
  `gc bd update "<workflow-root-id>" --set-metadata "gc.build.review_report_path=<absolute path>"`.
  Do not use `gc bd update --metadata 'key=value'`; `--metadata` only accepts
  a JSON object.
- From `$GC_RIG_ROOT`, run the artifact validator with the claimed bead id and
  fix any error before setting `gc.outcome=pass`:
  `GC_BEAD_ID=<claimed-step-id> .gc/scripts/checks/build-artifact-valid.sh`.
- On repair attempts (`gc.attempt` greater than 1), first read the validator
  errors from `gc.attempt_log` on the validation loop control bead (the
  dependent of this step bead) and fix every listed error in place.

Close with `gc.outcome=pass`.

Do not invoke provider-native subagents or provider-specific task tools.
