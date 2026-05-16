# Shakedown — Cross-Cutting Integration Validation

## Definition

A shakedown is the **first controlled, end-to-end exercise** of a modified producer-broker-consumer or client-store path using a **known canary payload**, under real operating conditions, with the declared delivery and consistency semantics observed and recorded.

It answers one question: **does this thing actually work when everything runs together?**

Concrete canary patterns and command sequences live in the tool-specific guideline files (`kafka_guidelines.md`, `rabbit_mq_guidelines.md`, `redis_guidelines.md`, `cosmosdb_guidelines.md`, `sql_guidelines.md`). This section defines what every shakedown must prove regardless of tool.

| Phase | Question |
|:------|:---------|
| Preflight | Is the environment ready to run? (credentials present, endpoint resolves, schema valid) |
| **Shakedown** | **Does the integrated path actually execute correctly via a real round-trip?** |
| Testing | Does it behave correctly under many cases or at scale? |

## Mandatory Triggers

Shakedown is required after any of:

- First deployment of a new producer, consumer, broker, topic, queue, exchange, stream, or data store client.
- Topology change to an existing producer-broker-consumer path or client-store path (partition count, replication factor, binding, policy, consistency level, partition key, cluster shard count).
- Delivery semantics change (at-most-once → at-least-once, at-least-once → exactly-once, auto-commit → manual commit, auto-ack → manual ack).
- Poison message or dead-letter handling change (DLQ topology, DLX routing, retry topic chain, max retry count, inbox deduplication).
- Credential, ACL, or authentication backend change affecting the service principal.
- Broker, store, or runtime version upgrade on any integration hop.
- Recovery after a systemic failure on any integration hop.
- Extended dormancy of a producer-consumer path whose environment has drifted.

**Cutover of any of the above without a recorded shakedown result is prohibited.** A successful unit test suite is **not** a substitute. A successful preflight is **not** a substitute.

## Non-Triggers

- Routine publish, consume, read, or write on an unchanged, previously validated path.
- Configuration value change within a previously validated schema and range.
- Scaling consumer or worker instance count within a validated consumer group or pool.
- Log level change in the client application.
- Content or data updates that do not change execution paths or delivery semantics.

## Validation Categories

1. **Message flow integrity** — the canary payload is received, deserialized, propagated through every declared hop, and delivered to the expected destination with its key, value, headers, and properties intact. No silent drops, no silent truncation, no silent reordering relative to the declared ordering guarantee.
2. **Broker and store connectivity** — every service-to-broker, service-to-store, and broker-to-broker hop establishes, authenticates, and exchanges the canary. Client libraries negotiate the declared protocol version, TLS cipher, authentication mechanism. Cluster members are all reachable; no partition leader missing; no shard unreachable.
3. **Resource availability** — connections, channels, sessions, consumer groups, partition assignments, slot ranges acquire and release cleanly. No unbounded growth in connection / channel / cursor count across the shakedown window. Ephemeral resources (reply queues, temporary subscriptions, pipelined transactions) clean up.
4. **Configuration propagation** — credentials flow from secret store to client and are actually usable, not merely present. Topic, queue, exchange, stream, key names resolve from configuration to the broker or store. Schemas register under the declared subject with the declared compatibility mode. Feature flags and environment overrides take effect at the components that consume them.
5. **Error handling paths** — a deliberately malformed canary routes to the DLQ, DLX, or inbox-rejected table. Retry and backoff fire as declared. Circuit breakers and publisher flow control trigger when injected with a broker throttle. Cleanup and compensation paths execute on a failed canary transaction. Error propagation stays within the declared failure domain.
6. **Side effect correctness** — at-least-once claims actually deliver at least once; exactly-once claims actually deliver exactly once; idempotent consumer claims actually deduplicate a replayed canary. External side effects (database writes, webhook calls, blob uploads) occur exactly as declared and target the correct destination. The outbox dispatches the canary event; the inbox deduplicates a replay.

## Execution Principles

- **Conservative execution** — a small, representative set of canaries. Not edge cases, not stress limits, not adversarial payloads.
- **Progressive stress** — start with the simplest happy-path canary; then the DLQ canary; then the failover or replay canary. **Stop at the first failure and diagnose.**
- **Controlled environment** — the real target broker or store, with production-equivalent topology, policies, and credentials. **Never** a mocked broker, in-memory store, or container that differs materially from target.
- **Observable execution** — capture client metrics, broker or store metrics, and full logs for the canary window. **A shakedown without observations is a shakedown that never happened.**
- **Known-good inputs** — canary payloads with deterministic keys, pre-computed hashes, and reserved shakedown namespaces so the canaries are identifiable in logs and metrics.
- **No optimization during shakedown** — note performance issues, log them, move on. Tuning during a shakedown invalidates the shakedown.

## Execution Pattern

1. Confirm preflight passes on every integration hop.
2. Initialize the client or producer in the controlled target environment with the service's actual credentials and configuration.
3. Execute the simplest end-to-end canary: produce, deliver, consume, ack, verify value intact.
4. Verify the canary reaches the correct destination with the declared delivery semantics.
5. Execute the DLQ/DLX/inbox-rejected canary and verify the poison path.
6. Execute the failover, replay, or idempotency canary if the change touched those paths.
7. Check for resource leaks: connections, channels, cursors, temporary resources.
8. Record all observations and classify the shakedown result.

## Result Classification

| Outcome | Trigger |
|:--------|:--------|
| `pass` | Every canary round-trips with the declared semantics; DLQ path routes the poison canary; failover or replay canary completes — proceed |
| `fail-blocking` | Canary does not reach the broker, store, or consumer; delivery semantics violated; DLQ path broken; idempotency claim violated; authentication denied — halt the change, fix the root cause, re-run the full shakedown |
| `fail-nonblocking` | Canary succeeds but latency exceeds the declared budget; non-critical metric warning; observable but non-blocking anomaly — log to the issue tracker with full diagnostic context and proceed with caution |
| `inconclusive` | Target broker or store unreachable during the window; leader election or shard migration in progress — adjust and re-run the specific validation |

## Required Artifacts

- Execution log with per-canary timestamps at every hop: produce, broker ack, deliver, consume, commit, side-effect confirmation.
- Result summary table: message flow integrity, broker and store connectivity, resource availability, configuration propagation, error handling, side effect correctness.
- Issue list: every observed anomaly classified as blocking, non-blocking, or deferred, with broker and client log excerpts.
- Environment snapshot: broker and store versions, client library versions, topology configuration, policy or ACL rules, credential identity, effective client configuration, TLS certificate fingerprint.

## Anti-Patterns

- Skipping shakedown after a "small" change that touched delivery semantics, DLQ routing, or authentication.
- Treating shakedown as a comprehensive integration test suite with many assertions.
- Running shakedown against a non-representative environment: mock broker, in-memory store, or differently configured container.
- Optimizing batch sizes, pool sizes, or timeouts during shakedown.
- Running shakedown without capturing logs, metrics, and an environment snapshot.
- Using auto-commit or auto-ack on the canary consumer, which hides commit-path failures.
- Claiming exactly-once or idempotent delivery without a canary that exercises the replay path.

## Tool-Specific References

| Domain | Reference |
|:-------|:----------|
| Kafka | `kafka_guidelines.md` Shakedown section |
| RabbitMQ | `rabbit_mq_guidelines.md` Shakedown section |
| Redis | `redis_guidelines.md` Shakedown section |
| Cosmos DB | `cosmosdb_guidelines.md` Shakedown section |
| SQL | `sql_guidelines.md` Shakedown section |

---
[Back to Overview](./OVERVIEW.md)
