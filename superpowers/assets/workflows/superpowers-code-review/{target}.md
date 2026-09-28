Finalize the Superpowers code-review expansion.

Verify the latest loop verdict from the code-review wrapper and
process-code-review lane.

Report-only path:

- If workflow root metadata `gc.var.review_mode=report`, do not require the
  process-code-review lane and do not apply fixes.
- Confirm the implementation review report exists at workflow root metadata
  `gc.build.code_review_report_path`.
- Confirm the gap-analysis report exists at workflow root metadata
  `gc.build.gap_analysis_report_path`.
- Preserve the reports' own verdicts (`approved`, `changes_required`, or
  `blocked`). In report mode, producing the validated reports is the successful
  deliverable even when findings require changes.
- Publish the implementation review report as the stage review report (see "Review report
  path" below).
- Update workflow root metadata:
  - `gc.build.code_review_status=reported`
  - `gc.build.code_review_report_path=<implementation review report path>`
- Close this expansion target with `gc.outcome=pass`,
  `code_review.verdict=reported`, and
  `code_review.report_path=<implementation review report path>`.

Approval path for `agent` and `interactive` modes:

- Confirm `code_review.verdict=done` on the process-code-review lane.
- Confirm the implementation review report exists at workflow root metadata
  `gc.build.code_review_report_path`.
- Confirm the gap-analysis report exists at workflow root metadata
  `gc.build.gap_analysis_report_path`.
- Confirm the review fix summary exists at workflow root metadata
  `gc.build.review_fix_summary_path`.
- Publish the implementation review report as the stage review report (see "Review report
  path" below).
- Update workflow root metadata:
  - `gc.build.code_review_status=approved`
  - `gc.build.code_review_approved_at=<UTC timestamp>`
- Close this expansion target with `gc.outcome=pass`,
  `code_review.verdict=done`, and
  `code_review.report_path=<review fix summary path>`.

Review report path (both passing paths):

The terminal artifact check on this step and the build gate validate the file
recorded at workflow root metadata `gc.build.review_report_path` against
`gc.build.review.v1`. The build prepare stage pre-declares that key as
`<artifact_root>/review-report.md`, which this expansion does not otherwise
write, so publish the review report explicitly before closing:

- Resolve the review report path: use workflow root metadata
  `gc.build.review_report_path` when it is set; otherwise use the implementation review report
  path from `gc.build.code_review_report_path`.
- If the review report path differs from the implementation review report path, copy the
  implementation review report to it with `mkdir -p "$(dirname "<review report path>")"`
  and `cp -f "<implementation review report path>" "<review report path>"`.
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

Failure path:

- If unresolved required findings remain, do not approve the expansion.
- Update workflow root metadata with `gc.build.code_review_status=failed`.
- Close with `gc.outcome=fail`, `code_review.report_path=<review fix summary
  path>`, and a concise `gc.failure_reason` that points at the blocking
  finding.
