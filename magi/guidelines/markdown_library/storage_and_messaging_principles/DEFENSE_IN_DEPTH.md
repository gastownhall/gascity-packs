# Defense in Depth

Multiple, independent layers protect storage and messaging systems from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

## Independent Layers of Defense

1. **Durability by replication** — All durable data MUST be replicated; a single copy is not durable regardless of disk class.
2. **Idempotency end-to-end** — Producers AND consumers MUST be idempotent; retries are inevitable.
3. **Dead-letter handling** — Every queue / topic / partition MUST have a defined poison-message destination.
4. **Monitoring of depth and latency** — Queue depth, age of oldest message, and end-to-end latency MUST be alerted on.
5. **Backup and restore drills** — Backups MUST be exercised by performing real restores at a documented cadence.
6. **Schema evolution discipline** — Schemas MUST be versioned and backwards-compatible; producers and consumers MUST roll independently.
7. **Rate limiting and backpressure** — Producers MUST experience backpressure when consumers cannot keep up; **unbounded buffering is forbidden**.

## The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule to data replicas, message brokers, and any leader-elected coordinator.

- **One is a claim** — One copy is not durable. One ack is not delivery.
- **Two is a tie** — Two copies tolerate one failure; they cannot resolve a conflict by majority and cannot tolerate a maintenance window without going to one.
- **Three is a quorum** — Three replicas (or three durable hops along a pipeline) are the **minimum that survive a single failure WHILE preserving a quorum** for conflict resolution.

**Example:** A pipeline with producer → broker → consumer plus an audit-store has three independent witnesses to every event; reconciliation across all three catches drops the broker alone does NOT detect.

---
[Back to Overview](./OVERVIEW.md)
