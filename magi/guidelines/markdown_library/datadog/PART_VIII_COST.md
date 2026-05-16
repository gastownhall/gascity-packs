# Part VIII: Cost Management

This section covers controlling Datadog costs while maintaining visibility.

## Understanding Datadog Pricing

### Cost Components

| Component                | Pricing Model             | Cost Driver                   |
|--------------------------|---------------------------|-------------------------------|
| **Infrastructure Hosts** | Per host/month            | Number of hosts               |
| **APM Hosts**            | Per host/month + spans    | Hosts with APM + trace volume |
| **Logs**                 | Per GB ingested + indexed | Log volume and retention      |
| **Custom Metrics**       | Per metric/month          | Unique metric timeseries      |
| **Synthetics**           | Per test run              | Test frequency and count      |
| **RUM**                  | Per session               | User session count            |

### Cost Visibility

Create a cost dashboard:

```yaml
dashboard:
  title: "Datadog Cost Analysis"
  widgets:
    - title: "Custom Metrics Count"
      query: "sum:datadog.estimated_usage.custom_metrics.total{*}"

    - title: "Log Ingestion (GB/day)"
      query: "sum:datadog.estimated_usage.logs.ingested_bytes{*} / 1e9"

    - title: "APM Spans Indexed"
      query: "sum:datadog.estimated_usage.apm.indexed_spans{*}"

    - title: "Cost by Service"
      query: "sum:datadog.estimated_usage.custom_metrics.total{*} by {service}"
```

## Log Cost Optimization

### Ingestion Controls

**Exclusion Filters**: Drop logs before indexing:
```yaml
exclusion_filters:
  - name: "Drop health checks"
    query: "source:nginx @http.url:/health"
    action: "drop"

  - name: "Drop debug logs in production"
    query: "env:prod level:DEBUG"
    action: "drop"

  - name: "Drop noisy third-party logs"
    query: "source:kubernetes @kubernetes.labels.app:kube-proxy"
    action: "drop"
```

**Sampling Filters**: Sample high-volume logs:
```yaml
sampling_filters:
  - name: "Sample successful requests"
    query: "source:nginx status:2*"
    sample_rate: 0.1  # Keep 10%

  - name: "Sample INFO logs"
    query: "level:INFO -@important:true"
    sample_rate: 0.5  # Keep 50%
```

### Retention Optimization

Configure multiple indexes with different retention:

```yaml
indexes:
  - name: "errors"
    filter: "status:error OR level:ERROR"
    retention: 90
    daily_limit: null  # No limit on errors

  - name: "security"
    filter: "@security:true"
    retention: 365  # Compliance requirement
    daily_limit: null

  - name: "application"
    filter: "level:(INFO OR WARN)"
    retention: 15
    daily_limit: 100GB

  - name: "debug"
    filter: "level:DEBUG"
    retention: 3
    daily_limit: 50GB
```

### Log Pipeline Optimization

Reduce log size through attribute remapping:

```yaml
processors:
  - type: "attribute-remapper"
    sources: ["kubernetes.pod.name"]
    target: "pod"

  - type: "attribute-remapper"
    sources: ["kubernetes.container.name"]
    target: "container"

  - type: "remover"
    sources:
      - "kubernetes.pod.uid"
      - "kubernetes.namespace.uid"
      - "kubernetes.node.uid"  # Remove high-cardinality unused fields
```

## Metric Cost Optimization

### Cardinality Reduction

Monitor and control metric cardinality:

```yaml
# High cardinality alert
alert:
  name: "High Cardinality Metric"
  query: |
    sum:datadog.estimated_usage.custom_metrics.by_metric{*} by {metric} > 10000
  message: |
    Metric {{metric}} has high cardinality ({{value}} timeseries).
    Review and reduce tag values.
```

### Metric Aggregation

Use metrics without tags for aggregated views:

```csharp
// Instead of per-request metrics with high cardinality
DogStatsd.Increment("requests", tags: new[] { $"user_id:{userId}" });  // BAD

// Use aggregated metrics
DogStatsd.Increment("requests", tags: new[] { $"tier:{tier}" });  // GOOD

// Store user-level detail in logs, not metrics
_logger.LogInformation("Request from user {UserId}", userId);
```

### Distribution Metric Percentiles

Limit distribution percentile storage:

```yaml
# In datadog.yaml
histogram_percentiles:
  - 0.50
  - 0.95
  - 0.99
  # Remove unnecessary percentiles like 0.75, 0.90
```

## Trace Cost Optimization

### Intelligent Sampling

Configure tail-based sampling to keep important traces:

```yaml
# In datadog-agent
apm_config:
  # Base sampling rate
  max_traces_per_second: 500

  # Keep all error traces
  analyzed_spans:
    - service: "*"
      sample_rate: 1.0
      condition: "error:true"

  # Keep all slow traces
  analyzed_spans:
    - service: "*"
      sample_rate: 1.0
      condition: "@duration:>5s"

  # Sample normal traces
  analyzed_spans:
    - service: "*"
      sample_rate: 0.1
```

### Span Filtering

Drop unnecessary spans:

```yaml
# Exclude health check spans
apm_config:
  ignore_resources:
    - "GET /health"
    - "GET /ready"
    - "GET /metrics"
    - "HEAD /"
```

### Retention Optimization

Configure trace retention based on value:

```yaml
# Shorter retention for routine traces
# Longer retention for error traces
retention_filters:
  - name: "error_traces"
    query: "status:error"
    retention: 30d

  - name: "slow_traces"
    query: "@duration:>5s"
    retention: 15d

  - name: "normal_traces"
    query: "*"
    retention: 7d
```

## Cost Allocation

### Tagging for Cost Attribution

Ensure all resources have cost allocation tags:

```yaml
required_tags:
  - team
  - service
  - cost_center
  - environment

tag_enforcement:
  on_missing: "warn"  # or "reject" for strict enforcement
```

### Cost Reporting by Team

```yaml
dashboard:
  title: "Cost by Team"
  widgets:
    - title: "Infrastructure Cost by Team"
      query: "sum:datadog.estimated_usage.hosts{*} by {team}"

    - title: "Log Cost by Team"
      query: "sum:datadog.estimated_usage.logs.ingested_bytes{*} by {team}"

    - title: "Custom Metrics by Team"
      query: "sum:datadog.estimated_usage.custom_metrics.total{*} by {team}"
```

---
[Back to Overview](./OVERVIEW.md)
