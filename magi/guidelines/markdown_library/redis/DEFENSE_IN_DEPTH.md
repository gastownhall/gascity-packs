# Defense in Depth

Multiple, independent layers protect Redis caches and data stores from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Persistence: AOF + RDB** — Production stores MUST run AOF + RDB; either alone has a failure mode the other compensates for. (Note: Azure Cache for Redis does not support AOF; use Enterprise tier or self-managed Redis where AOF + RDB is required.)
2. **Replication or cluster** — Standalone Redis is forbidden in production; use Sentinel HA or Redis Cluster.
3. **Monitoring of memory and evictions** — `maxmemory` + eviction policy + alerts on `evicted_keys` MUST be in place.
4. **Client-side retries and timeouts** — Clients MUST set explicit timeouts and retry on transient errors with backoff.
5. **Cache stampede protection** — Hot keys MUST be protected with single-flight or probabilistic early refresh.
6. **Backup snapshots shipped offsite** — RDB snapshots MUST be shipped to durable storage; volume snapshots are not enough.
7. **Schema discipline** — Keyspace conventions MUST be documented and enforced in code; ad-hoc keys are a leaking abstraction.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule to Redis HA topology.

- **One is a claim** — A single Redis node is unsafe; one process loss loses the data.
- **Two is a tie** — Primary + replica without an arbiter cannot perform a safe automatic failover (split-brain risk).
- **Three is a quorum** — Sentinel quorum MUST be three or more (and odd); Redis Cluster recommends three masters and three replicas. **Three voters are required for a clean failover decision.**

**Example:** A 2-Sentinel deployment in two AZs cannot reach a quorum if the AZs partition; adding a third Sentinel in a third AZ is the rule of three made literal.

---
[Back to Overview](./OVERVIEW.md)
