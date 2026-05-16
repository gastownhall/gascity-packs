# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Topic Naming | `domain.entity.event` lowercase with separators; no generic names |
| Partition Count | Size for peak parallelism and throughput; plan for no reduction |
| Partition Keys | High cardinality; stable per entity; prevent hot partitions |
| Replication Factor | Minimum 3 for production; set at creation |
| Min ISR | `replication_factor - 1`; ensures durability with availability |
| Producer Acks | `acks=all` for durable data; `enable.idempotence=true` |
| Consumer Commits | Manual commits after processing; no auto-commit for exactly-once |
| Offset Reset | `earliest` for replay capability; `latest` only for real-time |
| Serialization | Avro or Protobuf with Schema Registry; JSON for development only |
| Schema Evolution | Backward compatible by default; no breaking changes |
| Retention | Time-based for events; compact for entity state; compact+delete with tombstones for both |
| Error Handling | DLQ with error-context headers; retry-topic chain for backoff |
| Stream Processing | Kafka Streams for stateful business logic; ksqlDB for SQL aggregations |
| Security | SASL authentication; TLS 1.3 with `TLS_AES_256_GCM_SHA384`; least-privilege ACLs |
| Monitoring | Lag, under-replicated partitions, offline partitions, throughput |
| Consumer Groups | Cooperative sticky assignment; static membership in containers |
| Connect | Distributed mode; `errors.tolerance=all`; DLQ topic per connector |
| Transactions | Use for exactly-once across partitions; stable `transactional.id` |
| Tuning | Tuning profiles: high-throughput / low-latency / balanced — choose per workload |
| Capacity | RF + retention storage formula + 30% headroom; 10 Gbps min network; 32–64 GB RAM/broker |
| Shakedown | Real cluster + canary record + DLQ canary + rebalance canary; full classification + artifacts |
| Defense in Depth | RF=3 + idempotent producers + offset discipline + DLT + lag monitoring + rack/AZ + Schema Registry |
| Rule of Three | RF=3 / `min.insync=2`: two acknowledgments per write, third broker as hot spare |

---
[Back to Overview](./OVERVIEW.md)
