# Defense in Depth

Multiple, independent layers protect the Kafka cluster from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Replication factor** — Production topics MUST have `replication.factor=3` and `min.insync.replicas=2`.
2. **Idempotent producers** — Producers MUST set `enable.idempotence=true` and use transactions where exactly-once is required.
3. **Consumer offset discipline** — Auto-commit MUST be off for at-least-once consumers; offsets MUST be committed only after successful processing.
4. **Dead-letter topic** — Poison messages MUST be routed to a DLT; silent drops are forbidden.
5. **Monitoring of lag** — Consumer lag, ISR shrink/expand, under-replicated partitions MUST be alerted on.
6. **Rack or zone awareness** — Brokers MUST be distributed across racks/AZs; replicas MUST be placed accordingly.
7. **Schema Registry** — All payloads MUST go through a schema registry (Avro/Protobuf/JSON-Schema) so producers and consumers do NOT drift.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A single in-sync replica is the bare minimum and not durable; a single broker is unsafe.
- **Two is a tie** — RF=2 / `min.insync.replicas=1` means losing one broker loses the only durable copy and keeps producers writing into an unsafe state.
- **Three is a quorum** — RF=3 + `min.insync.replicas=2` is the canonical Kafka rule of three: two replicas MUST acknowledge before the producer considers the write durable, leaving the third as a hot spare. A broker fails with zero data loss and zero write disruption.

Example: losing the leader of a partition with RF=3 / `min.insync=2` still leaves two voters; the cluster elects a new leader from the surviving two without producer disruption.

---
[Back to Overview](./OVERVIEW.md)
