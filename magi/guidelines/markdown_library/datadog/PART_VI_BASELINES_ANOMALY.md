# Part VI: Performance Baseline and Anomaly Detection

This section covers establishing baselines and detecting deviations.

## Establishing Baselines

### Baseline Types

**Time-Based Baselines**:
- Hour-of-day patterns (traffic peaks at 2 PM)
- Day-of-week patterns (lower traffic on weekends)
- Monthly patterns (month-end processing spikes)
- Seasonal patterns (holiday shopping)

**Load-Based Baselines**:
- Latency vs. request rate correlation
- Error rate vs. concurrent users
- Resource usage vs. throughput

### Collecting Baseline Data

Minimum baseline collection period:
- Short-term: 2 weeks (covers weekday/weekend patterns)
- Medium-term: 1-3 months (covers monthly patterns)
- Long-term: 1 year (covers seasonal patterns)

**Baseline Metrics to Capture**:
```yaml
baseline_metrics:
  # Traffic patterns
  - name: http.requests.total
    aggregation: sum
    granularity: 1h
    retention: 90d

  # Latency patterns
  - name: http.requests.duration_ms
    aggregation: p50, p95, p99
    granularity: 5m
    retention: 30d

  # Error patterns
  - name: http.errors.total
    aggregation: sum
    granularity: 1h
    retention: 90d

  # Resource patterns
  - name: system.cpu.user
    aggregation: avg, max
    granularity: 5m
    retention: 30d
```

### Baseline Storage

Store baseline data for comparison:

```csharp
public class BaselineService
{
    public async Task RecordBaselineAsync(string metricName, double value, DateTime timestamp)
    {
        var baseline = new BaselineRecord
        {
            MetricName = metricName,
            Value = value,
            Timestamp = timestamp,
            HourOfDay = timestamp.Hour,
            DayOfWeek = timestamp.DayOfWeek,
            WeekOfYear = GetWeekOfYear(timestamp)
        };

        await _repository.SaveAsync(baseline);
    }

    public async Task<BaselineStats> GetBaselineAsync(string metricName, int hourOfDay, DayOfWeek dayOfWeek)
    {
        var historicalData = await _repository.GetAsync(
            metricName,
            hourOfDay: hourOfDay,
            dayOfWeek: dayOfWeek,
            lookbackWeeks: 4
        );

        return new BaselineStats
        {
            Mean = historicalData.Average(),
            StdDev = CalculateStdDev(historicalData),
            P95 = CalculatePercentile(historicalData, 95),
            Min = historicalData.Min(),
            Max = historicalData.Max()
        };
    }
}
```

## Anomaly Detection

### Datadog Anomaly Algorithms

**Basic**: Simple bounds based on historical data
```
anomalies(metric, 'basic', 2)  # 2 standard deviations
```

**Agile**: Quickly adapts to level shifts, good for metrics with trends
```
anomalies(metric, 'agile', 3)  # Agile with 3 bounds
```

**Robust**: Ignores outliers, good for noisy metrics
```
anomalies(metric, 'robust', 2)  # Robust with 2 bounds
```

### Anomaly Alert Configuration

```yaml
name: "Latency Anomaly"
type: "metric_alert"
query: |
  avg(last_4h):anomalies(
    avg:http.requests.duration_ms{service:order-api},
    'agile',
    3,
    direction='above'
  ) >= 1
message: |
  Latency for order-api is abnormally high.
  Current: {{value}}ms
  Expected range: {{threshold.lower}}ms - {{threshold.upper}}ms

  ## Investigation
  1. Check for recent deployments
  2. Check upstream dependencies
  3. Check for traffic spikes
  4. Review database query performance
```

### Forecast-Based Alerting

Alert on predicted future values:

```yaml
name: "Disk Space Forecast"
type: "metric_alert"
query: |
  max(next_1w):forecast(
    avg:system.disk.used{service:order-api},
    'linear',
    1
  ) > 0.9
message: |
  Disk usage is predicted to exceed 90% within 1 week.
  Current: {{value}}%
  Forecast: {{forecast_value}}%

  ## Action Required
  1. Increase disk size
  2. Implement log rotation
  3. Archive old data
```

## Distinguishing Application Issues from Load

### Load Correlation Analysis

**Latency vs. Load**:
```
# Compare latency trend with traffic trend
graph {
  metric_a: avg:http.requests.duration_ms{service:order-api}
  metric_b: sum:http.requests.total{service:order-api}.as_rate()
}
```

If latency increases proportionally with load: likely capacity issue
If latency increases without load increase: likely application issue

**Resource Saturation Check**:
```yaml
# Capacity dashboard
widgets:
  - title: "Latency vs. CPU"
    query_a: "avg:http.requests.duration_ms{service:order-api}"
    query_b: "avg:system.cpu.user{service:order-api}"

  - title: "Latency vs. Memory"
    query_a: "avg:http.requests.duration_ms{service:order-api}"
    query_b: "avg:system.mem.used{service:order-api} / avg:system.mem.total{service:order-api} * 100"

  - title: "Latency vs. DB Connections"
    query_a: "avg:http.requests.duration_ms{service:order-api}"
    query_b: "avg:db.connections.active{service:order-api}"
```

### Load vs. Application Issue Checklist

**Indicators of Load Issue**:
- [ ] Latency correlated with request rate
- [ ] CPU > 80%
- [ ] Memory > 85%
- [ ] Connection pool exhausted
- [ ] Queue depth increasing
- [ ] Scales well with more instances

**Indicators of Application Issue**:
- [ ] Latency increased after deployment
- [ ] Errors correlate with specific code path
- [ ] Problem persists regardless of load
- [ ] Specific endpoint affected
- [ ] New error types appearing
- [ ] Does not improve with more instances

### Automated Correlation

```csharp
public class CorrelationAnalyzer
{
    public CorrelationResult AnalyzeIncident(DateTime start, DateTime end, string service)
    {
        var latencyTimeSeries = GetMetric($"http.requests.duration_ms{{service:{service}}}", start, end);
        var loadTimeSeries = GetMetric($"http.requests.total{{service:{service}}}", start, end);
        var cpuTimeSeries = GetMetric($"system.cpu.user{{service:{service}}}", start, end);

        var loadCorrelation = CalculatePearsonCorrelation(latencyTimeSeries, loadTimeSeries);
        var cpuCorrelation = CalculatePearsonCorrelation(latencyTimeSeries, cpuTimeSeries);

        return new CorrelationResult
        {
            IsLoadRelated = loadCorrelation > 0.7,
            IsCpuRelated = cpuCorrelation > 0.7,
            LoadCorrelation = loadCorrelation,
            CpuCorrelation = cpuCorrelation,
            Recommendation = DetermineRecommendation(loadCorrelation, cpuCorrelation)
        };
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
