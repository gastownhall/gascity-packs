Record the current Superpowers reviews as the report-only loop terminal.

This lane is metadata-only. Do not edit product source, implementation
summaries, worktrees, either review report, or any adapter output.

Read the current attempt's `request-code-review` and `gap-analysis-review`
children and require each to be closed with `gc.outcome=pass`. Require their
recorded output paths to agree respectively with workflow root metadata
`gc.build.code_review_report_path` and
`gc.build.gap_analysis_report_path`. Require both canonical absolute files to
be contained by `gc.build.code_review_artifact_root`. Missing, ambiguous, or
earlier-attempt review children are blocking; do not reuse workflow-root paths
as substitutes.

Use the current implementation review at
`gc.build.code_review_report_path` as this terminal's report path. Preserve both
reports' semantic statuses (`approved`, `changes_required`, or `blocked`).
Report mode succeeds by delivering current findings; it does not authorize
fixes or turn required changes into approval. Set workflow root metadata
`gc.build.code_review_status=reported`.

Close the exact claimed bead with `gc.outcome=pass`,
`code_review.verdict=reported`, and identical
`code_review.report_path=<current implementation review path>` and
`code_review.output_path=<current implementation review path>` values. Do not
set `code_review.verdict=done`.

Do not invoke provider-native subagents or upstream plugin runtime commands.
This graph lane is the delegation mechanism.
