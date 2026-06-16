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
- Update workflow root metadata:
  - `gc.build.code_review_status=approved`
  - `gc.build.code_review_approved_at=<UTC timestamp>`
- Close this expansion target with `gc.outcome=pass`,
  `code_review.verdict=done`, and
  `code_review.report_path=<review fix summary path>`.

Failure path:

- If unresolved required findings remain, do not approve the expansion.
- Update workflow root metadata with `gc.build.code_review_status=failed`.
- Close with `gc.outcome=fail`, `code_review.report_path=<review fix summary
  path>`, and a concise `gc.failure_reason` that points at the blocking
  finding.
