Run the gstack QA loop.

This loop adapts upstream qa into browser QA, regression-test evidence,
synthesis, and one mode-selected terminal lane. It proves the product behavior,
not just the diff. Agent and interactive modes select `qa-fix-findings`; report
mode selects the structurally non-mutating `qa-report-findings` lane.

The selected terminal owns `code_review.verdict=done|iterate|reported` for the
loop. The synthesis lane owns the semantic
`code_review.review_verdict=approve|iterate` result.

Do not invoke provider-native subagents. Continue only through this Gas City
graph loop.
