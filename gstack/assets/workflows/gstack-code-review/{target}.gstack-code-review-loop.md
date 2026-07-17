Run the gstack code-review loop.

This loop has staff-engineer, QA-evidence, CSO security, and gap-analysis
lanes, followed by synthesis and one mode-selected terminal. In agent or
interactive mode, `apply-review-findings` owns
`code_review.verdict=done|iterate`. In report mode,
`report-review-findings` is read-only and owns
`code_review.verdict=reported` for the current attempt.

The implementation review check requires the selected current-attempt terminal;
a stale workflow-root report path cannot satisfy report mode.

Do not invoke provider-native subagents. Continue only through this Gas City
graph loop.
