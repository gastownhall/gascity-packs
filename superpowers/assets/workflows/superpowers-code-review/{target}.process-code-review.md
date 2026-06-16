Process Superpowers code-review feedback.

Use the installed `receiving-code-review` skill as guidance for triaging review
and gap-analysis findings. Resolve required findings in this single lane and
preserve traceability to the reviewer, finding id, file anchors, and acceptance
criteria.

Read the code-review context from workflow root metadata
`gc.build.code_review_context_path`, the implementation review report from
`gc.build.code_review_report_path`, and the gap-analysis report from
`gc.build.gap_analysis_report_path`. Write the review fix summary to workflow
root metadata path `gc.build.review_fix_summary_path`, which should be
`<artifact_root>/review-fix-summary.md`.

Use implementation target {{implementation_target}} for any code changes.
Close this lane only after the review-fix artifact records resolved findings,
changed files, tests run, and blockers. If there are no required fixes, record a
no-op review-fix artifact instead of editing code.

If the review-fix artifact includes `gc.build.review.v1` front matter, its
`trace.coverage[].status` values and Markdown coverage table statuses must use
only schema allowed coverage statuses: `covered`, `blocked`, `deferred`,
`not_applicable`, `out_of_scope`, or `superseded`. Use `covered` for resolved
findings; do not use `resolved`, `violated`, `approved`, or `changes_required`
as coverage statuses. Include `rationale: <why this id is not covered>` on
every non-`covered` coverage row. The Markdown coverage table remains ID/status
only; the rationale belongs in YAML front matter.

If both review lanes approve, perform a no-op pass, update workflow root
metadata with `gc.build.code_review_status=approved`, and close with
`code_review.verdict=done`. If required fixes remain after processing, update
workflow root metadata with `gc.build.code_review_status=draft` and close with
`code_review.verdict=iterate`.

Always close with `gc.outcome=pass`, `code_review.verdict=done|iterate`,
`code_review.report_path=<review fix summary path>`, and
`code_review.output_path=<review fix summary path>`.

Use the exact claimed bead id when updating metadata. Do not pass freeform notes
or additional positional arguments to `bd update`; unquoted words can resolve to
unrelated beads. Use this command shape:

```bash
bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'code_review.verdict=done' \
  --set-metadata 'code_review.report_path=<review fix summary path>' \
  --set-metadata 'code_review.output_path=<review fix summary path>'
bd close "$CLAIMED_BEAD_ID" --reason 'Code-review feedback processed and approved.'
```

Do not invoke provider-native subagents. This graph lane is the delegation
mechanism.
