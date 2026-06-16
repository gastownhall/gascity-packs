Finalize the gstack code review.

If workflow root metadata `gc.var.review_mode=report`, do not require the
apply-review-findings lane and do not apply fixes. Confirm the synthesized
review report exists at workflow root metadata `gc.build.code_review_report_path`.
Preserve the report's own verdict (`approved`, `changes_required`, or
`blocked`). In report mode, producing the validated report is the successful
deliverable even when findings require changes. Record
`gc.build.code_review_status=reported` on the workflow root and close with
`gc.outcome=pass`, `code_review.verdict=reported`, and
`code_review.report_path=<synthesized report path>`.

Verify the latest review loop approved the implementation: confirm
`code_review.verdict=done` on the apply-review-findings lane, the synthesized
review report at workflow root `gc.build.code_review_report_path`, and the
review-fix summary at `gc.build.review_fix_summary_path`. Record
`gc.build.code_review_status=approved` and
`gc.build.code_review_approved_at=<UTC timestamp>` on the workflow root for QA
and the final sprint report.

Close with `gc.outcome=pass`.

Do not invoke provider-native subagents or provider-specific task tools.
