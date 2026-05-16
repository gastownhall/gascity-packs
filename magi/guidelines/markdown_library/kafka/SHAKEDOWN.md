# Shakedown — End-to-End Cluster Validation

### Definition

A Kafka shakedown is the **first controlled producer-to-broker-to-consumer round-trip of a known canary message through the real broker cluster** after any change that touches topics, producers, consumers, schemas, Schema Registry, Connect, Streams, ACLs, or broker configuration.

It answers one question: *Does the message actually flow, end-to-end, through this cluster, with the declared semantics intact?*

| Compared To | Distinction |
|:------------|:------------|
| Health check | Health check queries broker liveness and controller state. Shakedown publishes a real message, commits an offset, and verifies the DLQ path. |
| Load test | Load test drives sustained throughput at limits. Shakedown sends a small, known payload through the happy path and observes. |

### Mandatory Triggers

- First deployment of a new topic, producer, consumer group, or Connect connector.
- Topic configuration change: partition count increase, replication factor change, cleanup policy change, retention change.
- Schema Registry compatibility mode change or schema evolution on a production subject.
- Broker upgrade, Kafka version upgrade, ZooKeeper-to-KRaft migration, tiered storage enablement.
- ACL modification affecting producer, consumer, or admin principals.
- Consumer group assignment strategy change (Range → Sticky → CooperativeStickyAssignor).
- Introduction or removal of transactional producers, idempotence settings, or `isolation.level`.
- DLQ topic topology change or retry topic chain modification.
- Recovery after broker partition loss, under-replicated partition incident, or offset reset.
- Topic dormancy exceeding retention period with no verified production traffic.

### Non-Triggers

- Routine producer execution against an unchanged topic.
- Adding a new consumer instance to an existing, validated consumer group with `CooperativeStickyAssignor`.
- Log level change in the client application.
- Monitoring dashboard or alert threshold adjustment.

### Validation Categories

1. **Topic existence and topology**
   - Topic exists with declared partition count and replication factor.
   - `min.insync.replicas` matches declared value.
   - `cleanup.policy`, `retention.ms`, `compression.type` propagated from the topic config source.
   - Partition leader assigned for every partition; no `OfflinePartitionsCount` on target topic.

2. **Schema Registry round-trip**
   - Canary schema registers under subject and passes the configured compatibility mode.
   - Producer serializes with `KafkaAvroSerializer` or `KafkaProtobufSerializer` against the live registry.
   - Consumer deserializes the canary with the same schema id.
   - Schema Registry cache population succeeds on both producer and consumer.

3. **Producer acknowledgment**
   - Producer with `acks=all` receives broker acknowledgment within the declared latency budget.
   - `enable.idempotence=true` holds the producer id across a forced retry of the canary send.
   - Transactional producer, if used, commits the canary transaction and `read_committed` consumer observes it atomically.
   - `record-error-rate == 0` during the canary window.

4. **Consumer delivery**
   - Consumer group joins coordinator and receives a partition assignment containing the canary partition.
   - Canary message is polled, deserialized, and processed exactly once per consumer group.
   - Offset commit succeeds under `enable.auto.commit=false` with explicit `commitSync`.
   - `records-lag-max` returns to zero after the canary is consumed.

5. **Dead-letter path**
   - A deliberately malformed canary routes to the declared `{topic}.dlq`.
   - Error context headers propagate to the DLQ record.
   - Main consumer group does not stall on the poison canary.

6. **Rebalance behavior**
   - Adding a consumer instance completes rebalance within the declared budget.
   - `CooperativeStickyAssignor` revokes only the partitions being reassigned.
   - In-flight canary processing completes without duplicate delivery across the rebalance.

7. **Authentication and authorization**
   - SASL/SCRAM, OAUTHBEARER, or mTLS handshake succeeds with the service principal.
   - Producer ACL grants WRITE on the canary topic; consumer ACL grants READ on topic and consumer group.
   - TLS negotiates the declared protocol (TLSv1.3) and cipher suite.

### Execution Principles

- **Conservative** — send a single well-formed canary record with a known key and known payload, then a single malformed canary for the DLQ path. Nothing else.
- **Progressive stress** — validate the happy path first; add the DLQ canary; add the rebalance canary; stop at the first failure and diagnose.
- **Controlled environment** — dedicated canary topic in the target cluster, or a staging cluster with production-equivalent broker configuration, replication factor, and Schema Registry.
- **Observable execution** — capture producer and consumer client metrics, broker JMX metrics for the canary topic, and full client logs at DEBUG for the duration.
- **Known-good inputs** — canary payload has a pre-computed expected hash and a deterministic key that maps to a known partition.
- **No optimization during shakedown** — do not tune `batch.size`, `linger.ms`, or `fetch.min.bytes` while the shakedown is in flight.

### Execution Sequence

| Step | Action |
|:----:|:-------|
| 1 | Confirm preflight: broker reachable, Schema Registry reachable, ACLs in place, topic created with declared configuration |
| 2 | Initialize producer with `acks=all`, `enable.idempotence=true`, declared `transactional.id` if transactions are used |
| 3 | Produce one canary record with a known key and payload; wait for ack within the latency budget |
| 4 | Poll with the canary consumer group until the canary record is received; verify key, value, headers, and offset |
| 5 | Commit the consumer offset explicitly; verify `records-lag-max` returns to zero |
| 6 | Produce one malformed canary; verify it lands in `{topic}.dlq` with error headers populated |
| 7 | Add a second consumer instance; verify rebalance completes within budget and no canary is duplicated |
| 8 | Record all client and broker observations; classify the shakedown result |

### Canary Producer/Consumer Configuration

```properties
canary.topic={domain}.{entity}.shakedown
canary.key=shakedown-{timestamp}
canary.payload={known-good-avro-record}
canary.expected.partition=0

# Producer
acks=all
enable.idempotence=true
delivery.timeout.ms=30000

# Consumer
group.id=shakedown-canary-{service}
enable.auto.commit=false
isolation.level=read_committed
auto.offset.reset=earliest
```

### Result Classification

- **Pass** — canary round-trip succeeds, DLQ path routes the poison canary, rebalance completes within budget, `records-lag-max` returns to zero. Proceed with the change.
- **Fail-blocking** — producer receives no ack, consumer does not join, schema incompatibility rejects the canary, DLQ does not route, or ACL denies the canary principal. Halt the change, fix the root cause, re-run the full shakedown.
- **Fail-nonblocking** — ack latency exceeds budget but the canary commits; rebalance completes above budget but eventually converges; non-critical metric warning. Log to the issue tracker with full diagnostic context and proceed with caution.
- **Inconclusive** — canary topic or Schema Registry unreachable during the window; broker controller election in progress. Adjust and re-run the specific validation.

### Required Artifacts

- Execution log with producer send timestamps, broker ack timestamps, consumer poll timestamps, and commit timestamps.
- Result summary table: topic topology, schema compatibility, producer ack, consumer delivery, DLQ path, rebalance behavior, ACLs.
- Issue list — every observed anomaly classified blocking, non-blocking, or deferred, with client and broker log excerpts.
- Environment snapshot: broker version, Kafka client version, Schema Registry version, topic config dump, ACL list, effective producer and consumer configuration.

### Anti-Patterns (Forbidden)

- Skipping shakedown after a "small" topic config change that touched replication factor or cleanup policy.
- Treating shakedown as a comprehensive consumer test suite with dozens of payload variants.
- Running shakedown against an embedded broker or mock Schema Registry instead of the target cluster.
- Tuning `batch.size` or `linger.ms` while the canary is in flight.
- Running a shakedown without capturing broker JMX metrics or client logs.
- Using auto-commit for the canary consumer, which hides offset commit failures.

---
[Back to Overview](./OVERVIEW.md)
