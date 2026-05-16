# Monitoring and Diagnostics

### Key Metrics

**Performance:**

| Metric | Threshold |
|:-------|:----------|
| `GET` latency / `SET` latency | p99 > 10ms — warning |
| `operations_per_second` | Sustained > 80% capacity — warning |
| `slow_queries` | > 10/minute — info |

**Memory:**

| Metric | Threshold |
|:-------|:----------|
| `used_memory_percentage` | > 80% — warning |
| `evicted_keys` | > 0 — warning |
| `fragmentation_ratio` | > 1.5 — info |

**Connections:**

| Metric | Threshold |
|:-------|:----------|
| `connected_clients` | > 80% of limit — warning |
| `rejected_connections` | > 0 — error |
| `client_output_buffer` | > 10MB — warning |

**Persistence:**

| Metric | Threshold |
|:-------|:----------|
| `rdb_last_save_time` | > 2× configured interval — warning |
| `rdb_changes_since_last_save` | > 10000 — info |

### Azure Monitor Integration

Azure Cache for Redis integrates with Azure Monitor:

- Metrics available in Azure Portal, exportable to Log Analytics.
- Alerts configurable on critical metrics (memory usage, server load, connection count).
- Diagnostics logs for detailed operation logging.
- Metrics granularity: 1-minute intervals standard; shorter for troubleshooting.

```kql
// Find operations with high latency
AzureMetrics
| where ResourceType == "REDIS"
| where MetricName in ("getlatency", "setlatency")
| summarize avg(Average), percentile(Average, 99) by bin(TimeGenerated, 5m)
| where percentile_Average_99 > 10
```

### Slow Log

Redis logs commands exceeding time threshold:

- Configuration: `slowlog-log-slower-than` (microseconds).
- Retrieval: `SLOWLOG GET 10` returns last 10 slow commands.
- Analysis: identify expensive operations, inefficient commands, missing indexes.

### Memory Analysis

| Command | Purpose |
|:--------|:--------|
| `MEMORY DOCTOR` | Redis recommendations for memory issues |
| `MEMORY USAGE key` | Memory consumed by specific key |
| `MEMORY STATS` | Detailed memory breakdown |
| `DEBUG OBJECT key` | Internal object encoding information |

### Application-Level Monitoring

- Instrument Redis calls — track latency, error rate, cache hit rate.
- Cache hit ratio: `hits / (hits + misses)` — **target 90%+ for effective caching**.
- Connection pool stats: utilization, wait time, exhaustion events.
- Distributed tracing: include Redis spans in traces for end-to-end visibility.

---
[Back to Overview](./OVERVIEW.md)
