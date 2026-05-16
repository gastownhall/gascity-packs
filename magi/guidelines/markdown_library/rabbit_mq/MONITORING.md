# Monitoring and Observability

### Key Metrics

**Queue metrics:**

| Metric | Meaning |
|:-------|:--------|
| `messages_ready` | Messages awaiting delivery |
| `messages_unacknowledged` | Delivered but not acknowledged |
| `message_rate` | Publish/deliver/acknowledge rates |
| `consumers` | Active consumer count |
| `memory` | Queue memory usage |

**Connection/channel metrics:**

| Metric | Meaning |
|:-------|:--------|
| `connections` | Total connection count |
| `channels` | Total channel count |
| `connection_rate` | Connection creation rate |

**Node metrics:**

| Metric | Meaning |
|:-------|:--------|
| `mem_used` | Memory consumption |
| `disk_free` | Available disk space |
| `fd_used` | File descriptor usage |
| `sockets_used` | Socket consumption |
| `gc_runs` | Erlang garbage collection frequency |

### Management Plugin

Enable the management plugin for web UI and HTTP API:

- Visual topology exploration.
- Real-time metrics and graphs.
- Queue and exchange management.
- User administration.

**Expose only to trusted networks.** The management API reveals sensitive operational data.

### Prometheus Integration

Export metrics to Prometheus for alerting and dashboards:

- Enable `rabbitmq_prometheus` plugin.
- Scrape `/metrics` endpoint.
- Build Grafana dashboards from standard templates.
- Alert on queue depth, consumer lag, memory pressure.

### Alerting Rules

Essential alerts:

| Condition | Severity |
|:----------|:---------|
| `queue_depth > threshold` | Warning — consumer lag |
| `memory_usage > 80%` | Critical — OOM risk |
| `disk_free < 1GB` | Critical — disk space |
| `consumers = 0` on production queue | Error |
| `connection_rate > normal × 10` | Warning — spike |
| `dlq_depth > 0` | Warning — dead letters accumulating |

### Distributed Tracing

Propagate trace context through messages:

- Include trace ID in message headers.
- Consumers extract and continue trace.
- Correlate publish, route, and consume spans.
- Integrate with Jaeger, Zipkin, or cloud tracing.

### Log Aggregation

Aggregate RabbitMQ logs for debugging:

- Connection events
- Channel errors
- Authentication failures
- Queue/exchange operations

Correlate with application logs using message IDs and correlation IDs.

---
[Back to Overview](./OVERVIEW.md)
