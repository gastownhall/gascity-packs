Run the build-basic starter factory review loop.

The child beads refresh provenance, run three review lanes, synthesize, then
either report or apply fixes:
acceptance/correctness, test evidence, and simplicity/maintainability. These are
starter factory lanes: broad enough to demonstrate Gas City fanout/fanin, but
small enough for first-time factory users to understand.

In report mode the read-only terminal owns `code_review.verdict=reported` and
completes after recording either approvals or required findings. Other modes use
apply-review-findings with `code_review.verdict=done|iterate` and repeat until all
three lanes approve. Every lane, synthesis, and terminal must carry the same live
`code_review.review_input_snapshot`, binding the canonical summary and review
context paths and bytes. Any implementation or review-input change invalidates
earlier approvals and requires another iteration.

Do not invoke provider-native subagents. Continue only through this Gas City
graph loop.
