Record the current Compound Engineering review as the report-only loop
terminal.

This lane is metadata-only. Do not edit product source, implementation
summaries, worktrees, the synthesized review report, or any adapter output.

Read the current attempt's `synthesize-code-review` child and require it to be
closed with `gc.outcome=pass`. Read its exact
`code_review.review_report_path` and `code_review.output_path`, require those
paths to agree with workflow root metadata
`gc.build.code_review_report_path`, and require that canonical absolute file to
be contained by `gc.build.code_review_artifact_root`. A missing, ambiguous, or
earlier-attempt synthesis is blocking; do not reuse a workflow-root path as a
substitute.

Preserve the synthesized artifact's semantic status (`approved`,
`changes_required`, or `blocked`). Report mode succeeds by delivering current
findings; it does not authorize fixes or turn required changes into approval.
Set workflow root metadata `gc.build.code_review_status=reported`.

Close the exact claimed bead with `gc.outcome=pass`,
`code_review.verdict=reported`, and identical
`code_review.report_path=<current synthesized report path>` and
`code_review.output_path=<current synthesized report path>` values. Do not set
`code_review.verdict=done`.

Do not invoke provider-native subagents. This graph lane is the delegation
mechanism.
