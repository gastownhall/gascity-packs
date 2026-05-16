# Shakedown — Integration Validation

### Definition

A RabbitMQ shakedown is **a controlled publish-exchange-queue-consume round-trip of a known canary message through the real broker** after any change that touches topology, publishers, consumers, policies, vhosts, users, or cluster configuration. The shakedown validates the declared topology exists, matches the desired binding graph, and delivers end-to-end with the declared acknowledgment and dead-letter semantics.

| Distinct from | Difference |
|:--------------|:-----------|
| Health check | Polls broker liveness and node status; shakedown publishes a canary, observes traversal of exchange→binding→queue, manually acks, and verifies the DLX path |
| Load test | Drives PerfTest at sustained rates; shakedown sends a handful of representative canaries and inspects the outcome |

### Mandatory Triggers

Shakedown is mandatory after any of:

- First deployment of a new exchange, queue, binding, or consumer application.
- Policy change affecting HA, quorum, lazy mode, TTL, max-length, or DLX routing.
- Migration between classic and quorum queue types.
- Vhost creation, user creation, or permission modification affecting the service principal.
- Broker upgrade, Erlang upgrade, or plugin enablement.
- Cluster topology change: node addition, node removal, partition handling strategy change.
- TLS certificate rotation or authentication backend change (internal → LDAP → OAuth2 → x509).
- Federation or shovel link creation between brokers.
- Recovery after a network partition, node restart under `pause_minority`, or queue leader election.
- Reintroduction of a dormant queue whose topology has drifted from source declarations.

### Non-Triggers

- Routine publishing against an unchanged topology.
- Scaling consumer instance count on an existing, validated work queue.
- Adjusting client-side prefetch within the validated range.
- Log level change in the consumer application.

### Validation Categories

1. **Topology declaration** — all required exchanges declared idempotently with the correct type; all required queues declared with correct durability, `x-queue-type`, and `x-dead-letter-exchange` arguments; all bindings present connecting exchanges to queues with correct routing keys or header match rules; passive declarations confirm existence without redefining parameters.
2. **Publisher confirm round-trip** — publisher enables confirms and receives `basic.ack` for the canary within the declared latency budget; mandatory flag returns `basic.return` only for deliberately unroutable probes; publisher handles `basic.nack` by the declared backoff path.
3. **End-to-end delivery** — canary message arrives in every queue bound to the target exchange under the canary routing key; consumer on each bound queue receives, processes, and manually acks the canary; message properties survive the round-trip (`content_type`, `delivery_mode`, `message_id`, `correlation_id`, `timestamp`); `messages_ready` and `messages_unacknowledged` return to zero after the canary.
4. **Dead-letter exchange routing** — rejected canary with `requeue=false` routes to the declared DLX with the declared routing key; TTL-expired canary routes to the DLX and arrives at the DLQ; queue length limit exceeded routes overflowed canaries according to `x-overflow`; DLQ consumer receives the dead-lettered canary with `x-death` headers populated.
5. **Policy and argument propagation** — policies matching the canary queue apply their declared arguments (HA, quorum replication factor, lazy mode, max-length); quorum queue leader and followers report healthy via `rabbitmqctl list_queues`; priority canary delivered ahead of baseline-priority canaries.
6. **Consumer semantics** — manual ack path holds: `nack requeue=true` triggers redelivery, `nack requeue=false` triggers DLX; prefetch limit bounds in-flight canaries as declared; consumer cancel and reconnect recovers the canary flow without message loss.
7. **Authentication and transport** — TLS handshake succeeds on port 5671 with the declared cipher and certificate chain; service user authenticates via the declared backend and holds `configure`, `write`, `read` permissions on the canary resources; heartbeat frames flow at the declared interval; connection is not closed.

### Execution Principles

- **Conservative execution** — publish one well-formed canary per exchange, one deliberately unroutable probe, one rejected canary for DLX, one TTL-expired canary. No more.
- **Progressive stress** — validate declarations first, then confirms, then delivery to every bound queue, then DLX paths, then failover behavior. Stop at the first failure and diagnose.
- **Controlled environment** — use a dedicated canary vhost or the target vhost with canary-prefixed resources, against the target broker or a cluster with identical node count, queue type, and policy set.
- **Observable execution** — enable `rabbitmq_management` plugin metrics; capture publisher confirm counts, queue metrics, and consumer delivery logs for the shakedown window.
- **Known-good inputs** — canaries carry a deterministic `message_id`, a pre-computed payload hash, and a known routing key that exercises the target binding.
- **No optimization during shakedown** — do not retune prefetch, heartbeat, or `vm_memory_high_watermark` while the canary is in flight. Record observations and address after classification.

### Execution Pattern

1. Confirm preflight: broker reachable on 5671, management API reachable, service user authenticates, target vhost exists.
2. Declare or passively verify the canary topology: exchanges, queues, bindings, policies.
3. Enable publisher confirms and publish one canary to the target exchange with the canary routing key.
4. Await `basic.ack` within the confirm latency budget; record the confirm path.
5. Consume from each bound queue; verify the canary arrives, properties intact, and manually ack.
6. Publish one canary designed to be rejected with `requeue=false`; verify DLX routing to the DLQ with `x-death` headers.
7. Publish one canary with a short `x-message-ttl`; verify TTL expiry routes to the DLX.
8. Record all observations; classify the shakedown result.

### Canary Topology

| Element | Format | Arguments |
|:--------|:-------|:----------|
| Exchange | `{domain}.shakedown.topic` | `type=topic`, `durable=true` |
| Main queue | `{service}.shakedown.main` | `x-queue-type=quorum`, `durable=true`, `x-dead-letter-exchange={domain}.shakedown.dlx`, `x-max-length=100`, `x-overflow=reject-publish-dlx` |
| DLQ | `{service}.shakedown.dlq` | `x-queue-type=quorum`, `durable=true` |
| Binding | `{domain}.shakedown.topic` → `{service}.shakedown.main` | routing key `canary.#` |

### Result Classification

| Outcome | Meaning |
|:--------|:--------|
| `pass` | Canary traverses exchange to every bound queue, publisher confirm arrives within budget, DLX routes rejected and expired canaries, properties intact, queues return to zero depth — proceed |
| `fail-blocking` | Publisher confirm never arrives, canary never reaches a bound queue, DLX routing fails, manual ack path is broken, or authentication denies the service user — halt the change, fix the root cause, re-run the full shakedown |
| `fail-nonblocking` | Confirm latency exceeds budget but succeeds; non-critical queue metric warning; policy applies on a delay — log to the issue tracker with full diagnostic context and proceed with caution |
| `inconclusive` | Management API unreachable during the window; cluster leader election in progress on the canary queue — adjust and re-run the specific validation |

### Required Artifacts

- Execution log with publish, confirm, deliver, and ack timestamps per canary.
- Result summary: topology declaration, publisher confirm, end-to-end delivery per bound queue, DLX routing, policy propagation, consumer semantics, transport.
- Issue list: every anomaly classified blocking, non-blocking, or deferred, with broker logs and management API snapshots.
- Environment snapshot: broker version, Erlang version, cluster node list, effective policies, queue type per canary queue, vhost permissions, TLS certificate fingerprint.

### Anti-Patterns

- Skipping shakedown after a "small" policy change that touched HA or DLX routing.
- Treating shakedown as a comprehensive consumer integration suite with many payload variants.
- Running shakedown against an in-memory broker or a single-node cluster when the target is a multi-node quorum cluster.
- Retuning prefetch or heartbeat while the canary is in flight.
- Running shakedown without capturing management API queue metrics and `rabbitmqctl` output.
- Auto-ack on the canary consumer, which hides broken manual-ack paths.

---
[Back to Overview](./OVERVIEW.md)
