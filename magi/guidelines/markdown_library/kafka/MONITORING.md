# Monitoring and Operations

### Broker Metrics

| Metric | Threshold | Action |
|:-------|:----------|:-------|
| `UnderReplicatedPartitions` | `> 0` | Investigate broker health immediately |
| `OfflinePartitionsCount` | `> 0` | Immediate intervention required |
| `ActiveControllerCount` | `!= 1` | Exactly one controller required |
| `BytesInPerSec` / `BytesOutPerSec` | — | Track network throughput per broker |
| `RequestHandlerAvgIdlePercent` | `< 30%` | Broker overloaded |

### Producer Metrics

| Metric | Threshold | Action |
|:-------|:----------|:-------|
| `record-send-rate` | — | Track messages/sec sent |
| `record-error-rate` | `> 0` | Investigate failed sends |
| `request-latency-avg` | `> 100 ms` | Check network and broker load |
| `batch-size-avg` | — | Indicates batching efficiency |

### Consumer Metrics

| Metric | Threshold | Action |
|:-------|:----------|:-------|
| `records-consumed-rate` | — | Messages processed/sec |
| `records-lag-max` | Approaching retention period | Scale consumers or optimize processing |
| `commit-latency-avg` | — | Time to commit offsets |
| `rebalance-latency-avg` | `> 30 s` | Consider static membership |

### Alerting Tiers

**Critical (page immediately):**

- `OfflinePartitionsCount > 0`.
- `UnderReplicatedPartitions > 0` for extended period.
- `ActiveControllerCount != 1`.
- Consumer lag exceeding retention period risk.

**Warning (investigate within hours):**

- Consumer lag sustained increase.
- Broker disk usage above 70%.
- Request handler idle below 50%.
- Producer error rate above 0.

### Log Management

Kafka broker logs:

- `server.log` — main broker log; request handling, errors.
- `controller.log` — controller-specific operations.
- `state-change.log` — partition leadership changes.
- `kafka-request.log` — optional request logging for debugging.

Configure log retention and rotation. Ship logs to centralized logging platform. Correlate broker logs with client-side logs for troubleshooting.

---
[Back to Overview](./OVERVIEW.md)
