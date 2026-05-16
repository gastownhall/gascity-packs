# Defense in Depth

Multiple, independent layers protect Datadog observability from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Metrics** — Critical signals (RED: rate, errors, duration; or USE: utilization, saturation, errors) MUST be emitted as metrics.
2. **Logs** — Structured logs MUST be shipped with trace IDs so they are joinable to traces.
3. **Traces** — Distributed traces MUST cover every cross-service call; sampling MUST preserve all error traces.
4. **Synthetics** — Synthetic monitors MUST exercise critical user flows from multiple regions.
5. **Real User Monitoring** — RUM MUST capture client-side errors and Core Web Vitals on user-facing apps.
6. **Alerts and SLOs** — SLOs MUST be defined for every critical service; alerts MUST be tied to SLOs, not raw thresholds.
7. **Dashboards and runbooks** — Each alert MUST link to a dashboard and a runbook; **an alert without context wakes humans up to do nothing.**
8. **Shakedown** — The telemetry-pipeline shakedown above covers the path the dashboard cannot.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A single signal (e.g., error rate) is one voter; it tells you something is wrong, not what or where.
- **Two is a tie** — Two signals give a contradictory story (e.g., logs say success, latency spikes); without a third, the operator cannot triage.
- **Three is a quorum** — **Metrics + logs + traces** are the canonical observability triple. Every incident triage MUST cross-reference all three; a hypothesis is held only when at least two corroborate it.

Example: a latency alert that traces show is upstream + logs show as 502 from a specific dependency = three voters converging on the real cause; one signal alone produces guesses.

---
[Back to Overview](./OVERVIEW.md)
