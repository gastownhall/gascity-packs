# Defense in Depth

Multiple, independent layers protect the RabbitMQ cluster from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Quorum queues** — Production queues MUST be quorum queues (Raft-based); classic mirrored queues are deprecated and MUST be migrated.
2. **Publisher confirms** — Publishers MUST enable confirms and treat unconfirmed messages as failed.
3. **Consumer acknowledgments** — Consumers MUST use manual ack and ack only after successful processing.
4. **Dead-letter exchange** — Every queue MUST route to a DLX so poison messages are observed, not lost.
5. **Monitoring and alerts** — Queue depth, consumer count, message rate, and unacked count MUST be alerted on.
6. **Clustered deployment** — Production MUST run a 3-node (or 5-node) cluster across distinct hosts/AZs.
7. **Backup of definitions** — Exchange/queue/binding definitions MUST be exported regularly so a cluster is rebuildable.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule to RabbitMQ cluster sizing and queue replication.

- **One is a claim** — A single-node RabbitMQ is unsafe; one process loss loses every classic queue and every quorum queue's availability.
- **Two is a tie** — Two-node clusters cannot establish a Raft quorum; a partition causes a split brain or a stop.
- **Three is a quorum** — Quorum queues require an odd cluster size of three or more to elect leaders. **Three nodes is the canonical RabbitMQ rule of three:** one fails with no message loss and no availability impact.

**Example:** A 3-node cluster surviving the loss of one node still has 2 of 3 voters and continues producing, consuming, and replicating without operator intervention.

---
[Back to Overview](./OVERVIEW.md)
