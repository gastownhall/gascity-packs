Run the Jev-gated review loop.

The child beads are the review lanes the Jev gate kept (gate: {gate}), an
optional synthesis, and fix application. Lanes the gate cleared do not exist in
this loop. Gate scope: acceptance={acceptance} (criteria: {acceptance_scope}),
test_evidence={test_evidence}, simplicity={simplicity} (scope:
{simplicity_scope}), synthesis={synth}.

The apply-review-findings lane owns `code_review.verdict=done|iterate` and
`code_review.report_path=<review summary path>`. The implementation review
check repeats this loop until the latest verdict is `done`.

Do not invoke provider-native subagents. Continue only through this Gas City
graph loop.
