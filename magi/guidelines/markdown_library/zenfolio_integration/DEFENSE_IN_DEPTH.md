# Defense in Depth

Multiple, independent layers protect the Zenfolio API integration from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Seven Independent Layers of Defense

| Layer | Validation |
|:-----:|:-----------|
| 1 | **Schema validation** — Every Zenfolio response MUST be validated against an explicit schema before deserialization |
| 2 | **Retry with backoff** — Outbound calls MUST retry with exponential backoff on 5xx and 429 |
| 3 | **Circuit breaker** — Trips after sustained failures so the integration does **not** DDoS Zenfolio or itself |
| 4 | **Local cache with TTL** — Read paths MUST cache with a TTL appropriate for the data; the cache is the **second source of truth** when the upstream is degraded |
| 5 | **Dead-letter queue** — Failed mutations MUST land in a DLQ for replay; **silent drops are forbidden** |
| 6 | **Monitoring and alerts** — Latency, error rate, and DLQ depth MUST be alerted on |
| 7 | **Scheduled reconciliation** — A scheduled job MUST diff local copies of Zenfolio data against fresh API reads |

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule whenever a decision in this domain depends on a check, a copy, a vote, or an actor that fails, drifts, or disagrees.

- **One is a claim** — A successful API call is one signal; Zenfolio accepted the request and the local copy is still pending commit.
- **Two is a tie** — API success + cache hit serving stale data is the consistency dissent; **reconciliation is the deciding voter**.
- **Three is a quorum** — Live API + cache + reconciliation job form the triple. **The integration's view of Zenfolio state is trustworthy only when at least two of these agree, and any disagreement raises an alert.**

**Example:** A photo upload returning 200 but never appearing in the gallery — only the reconciliation pass catches it.

---
[Back to Overview](./OVERVIEW.md)
