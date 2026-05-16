# Replication and Durability

### Replication Configuration

| Property | Value | Purpose |
|:---------|:------|:--------|
| `replication.factor` | **≥ 3 for production** | Number of copies including leader |
| `min.insync.replicas` | `replication_factor - 1` (i.e., 2 with RF=3) | Minimum replicas that must acknowledge before a write is committed |
| `unclean.leader.election.enable` | **`false`** | Disallow out-of-sync replicas to become leader |

With RF=3 and `min.isr=2`, one broker failure is tolerable. Setting `min.isr=1` defeats the purpose of replication. Enabling `unclean.leader.election=true` accepts data loss.

### ISR (In-Sync Replicas)

A replica is in-sync when:

- Connected to ZooKeeper/controller.
- Fetched from leader within `replica.lag.time.max.ms`.
- Not too far behind leader's log end offset.

When ISR shrinks below `min.insync.replicas`, writes fail with `NotEnoughReplicasException`. Monitor ISR shrinkage; it indicates broker health issues.

### Durability Guarantees

With `acks=all`, `min.insync.replicas=2`, `replication.factor=3`:

- Message survives any single broker failure.
- Write succeeds only when 2+ brokers have the message.
- If 2 brokers fail simultaneously before replication, data loss is possible.

For stricter guarantees, increase replication factor and `min.insync.replicas`. Cost is increased write latency and network traffic.

### Broker Failure Handling

When a leader fails:

1. Controller detects failure (ZooKeeper session timeout or heartbeat failure).
2. Controller selects new leader from ISR.
3. Clients refresh metadata and reconnect.
4. Producers retry in-flight requests.
5. Consumers continue from committed offsets.

This typically completes in seconds. Configure client timeouts to accommodate leader election without surfacing errors to applications.

---
[Back to Overview](./OVERVIEW.md)
