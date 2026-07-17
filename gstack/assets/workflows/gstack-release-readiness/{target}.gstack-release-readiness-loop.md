Run the gstack release readiness loop.

This loop adapts upstream document-release, ship, and land-and-deploy into
explicit Gas City lanes. It checks docs, PR readiness, deployment readiness,
and residual risk before finalization.

The synthesize-release-readiness lane owns `code_review.verdict=done|iterate`
for agent or interactive mode. In report mode, the current synthesis feeds the
read-only `report-release-findings` terminal, which owns
`code_review.verdict=reported`; a stale code-review report cannot satisfy this
loop.

Do not invoke provider-native subagents. Continue only through this Gas City
graph loop.
