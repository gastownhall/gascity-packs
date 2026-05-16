# Defense in Depth

Multiple, independent layers protect Cosmos DB from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Multi-region writes or replication** — Production accounts MUST be multi-region; single-region is a single point of failure.
2. **Consistency level discipline** — Consistency MUST be chosen explicitly per workload (Strong / Bounded Staleness / Session); never default.
3. **RU throughput monitoring** — RU consumption MUST be monitored and alerted before throttling occurs in production.
4. **Partition key validation** — Hot-partition detection MUST run; uneven distribution is a latent outage.
5. **Backup and PITR** — Continuous backup / point-in-time-restore MUST be enabled; restores MUST be exercised.
6. **TTL and retention** — TTL on transient containers MUST be set so unbounded growth does NOT fill the account.
7. **DR runbook** — A failover runbook MUST exist and MUST be drilled.
8. **Post-change shakedown** — §17 covers paths the metrics and unit suites cannot.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — Single-region Cosmos is one copy of the data — unsafe for production.
- **Two is a tie** — Two regions provide failover but cannot resolve a write conflict via majority.
- **Three is a quorum** — Three regions (or three replicas in the multi-master replica set) provide quorum-based conflict resolution **and** survive a region loss with two healthy voters remaining.

Example: a bounded-staleness account with three regions loses any one and still satisfies reads from the remaining majority — the rule of three made physical.

---
[Back to Overview](./OVERVIEW.md)
