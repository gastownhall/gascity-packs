# Replication and High Availability

### Standard Replication

Standard tier and above provide primary/replica replication:

- Synchronous replication — writes acknowledged after replica receives data.
- Automatic failover — replica promoted if primary fails.
- Failover time — seconds to low minutes depending on conditions.

### Zone Redundancy

Premium and Enterprise tiers support zone redundancy:

- Replicas distributed across availability zones.
- Survives zone failure without data loss.
- Higher latency for synchronous replication across zones.

### Geo-Replication

| Type | Tier | Behavior |
|:-----|:-----|:---------|
| Passive | Premium | Primary in one region; linked secondary in another; async replication; manual failover; secondary read-only until failover |
| Active | Enterprise | Multiple active caches in different regions; writes accepted in any region; CRDTs handle concurrent writes; no manual failover |

### Handling Failover in Applications

Failover causes brief unavailability:

- Existing connections may reset.
- Commands in flight may fail.
- Client reconnects to new primary.

**Application requirements:** retry logic with exponential backoff; idempotent operations where possible; accept that cache misses may increase during failover; circuit breaker to prevent retry storms.

**StackExchange.Redis failover handling:** automatic reconnection built in; configure `connectRetry` and reconnect backoff; events available for connection state changes.

---
[Back to Overview](./OVERVIEW.md)
