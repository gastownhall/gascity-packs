# Observability

### Metrics Collection

Deploy Prometheus or use Azure Monitor managed Prometheus:

- **Cluster metrics**: node utilization, pod status, resource consumption.
- **Application metrics**: request rate, error rate, latency distributions.
- **Custom metrics**: business KPIs exposed via application instrumentation.

Retention:

- Operational metrics: 15–30 days.
- Trend analysis: 90+ days.

### Logging Architecture

| Component | Behavior |
|:----------|:---------|
| Application | Write to stdout/stderr |
| Collection | DaemonSet aggregation (Fluentd, Fluent Bit, Azure Monitor agent) |
| Storage | Centralized platform (Azure Monitor, Elasticsearch, Loki) |

**Structured logging — JSON format with consistent fields:**

- `timestamp`
- `level`
- `message`
- `trace_id`
- `pod_name`

Unstructured logs complicate parsing and correlation.

### Distributed Tracing

- OpenTelemetry SDK instrumentation in applications.
- Trace context propagation via HTTP headers.
- Export to Azure Monitor Application Insights, Jaeger, or Zipkin.
- Sampling: 100% sampling expensive, 1% may miss rare issues. **Recommended: 10–20%** for production workloads.

### Alerting Strategy

Alert on symptoms, not causes:

| Severity | Examples |
|:---------|:---------|
| **Page-worthy** | Service unavailable, error rate exceeding SLO, critical security events |
| **Ticket-worthy** | Elevated latency, resource utilization approaching limits, certificate expiration approaching |
| **Dashboard-only** | Routine scaling events, successful deployments, informational events |

**Avoid alert fatigue — every alert should require human action.**

---
[Back to Overview](./OVERVIEW.md)
