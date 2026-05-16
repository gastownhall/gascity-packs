# Part VII: Incident Response with Datadog

This section covers using Datadog effectively during incident response.

## Incident Detection

### Automated Incident Creation

Configure Datadog to create incidents from alerts:

```yaml
incident_rule:
  name: "Auto-create incident for critical alerts"
  condition: "alert.severity == 'critical'"
  action:
    create_incident:
      severity: "SEV-1"
      commander: "@oncall-primary"
      notify:
        - "#incident-channel"
        - "@oncall-secondary"
```

### Incident Triage Dashboard

Build a triage-focused dashboard:

```yaml
dashboard:
  title: "Incident Triage - {{service}}"
  widgets:
    - title: "Current State"
      type: "group"
      widgets:
        - title: "Error Rate (now)"
          query: "sum:http.errors.total{service:$service}.as_rate()"
        - title: "p99 Latency (now)"
          query: "p99:http.requests.duration_ms{service:$service}"
        - title: "Request Rate (now)"
          query: "sum:http.requests.total{service:$service}.as_rate()"

    - title: "What Changed?"
      type: "group"
      widgets:
        - title: "Recent Deployments"
          type: "event_stream"
          query: "sources:deployment service:$service"
        - title: "Recent Config Changes"
          type: "event_stream"
          query: "sources:configuration service:$service"
        - title: "Alerts Timeline"
          type: "event_stream"
          query: "sources:alert service:$service"

    - title: "Error Analysis"
      type: "group"
      widgets:
        - title: "Errors by Type"
          query: "sum:http.errors.total{service:$service} by {error_type}"
        - title: "Error Logs"
          type: "log_stream"
          query: "service:$service status:error"

    - title: "Dependency Health"
      type: "group"
      widgets:
        - title: "Upstream Services"
          type: "service_map"
        - title: "Database Latency"
          query: "p99:db.queries.duration_ms{service:$service}"
        - title: "External API Latency"
          query: "p99:http.client.duration_ms{calling_service:$service} by {target_service}"
```

## Root Cause Analysis

### Trace Analysis Workflow

1. **Find Error Traces**:
```
service:order-api status:error @duration:>5s
```

2. **Identify Common Patterns**:
```
# Group errors by endpoint and error type
service:order-api status:error | stats count by resource_name, error.type
```

3. **Examine Specific Trace**:
- Open slowest/error trace
- Walk through span waterfall
- Identify where time is spent
- Check span tags for context

### Log Analysis Workflow

1. **Find Error Logs in Time Window**:
```
service:order-api level:ERROR timestamp:[incident_start TO incident_end]
```

2. **Group by Pattern**:
```
service:order-api level:ERROR | pattern
```

3. **Find First Occurrence**:
```
service:order-api level:ERROR "specific error message" | sort timestamp asc | head 1
```

4. **Correlate with Traces**:
```
service:order-api level:ERROR @trace_id:abc123
```

### Deployment Correlation

1. **Find Recent Deployments**:
```
sources:deployment service:order-api timestamp:[1h ago TO now]
```

2. **Compare Before/After**:
```yaml
comparison:
  metric: "sum:http.errors.total{service:order-api}"
  before: "2024-06-20T14:00:00Z TO 2024-06-20T14:30:00Z"  # Before deploy
  after: "2024-06-20T14:30:00Z TO 2024-06-20T15:00:00Z"   # After deploy
```

3. **Diff Versions**:
- Link to commit diff in deployment event
- Check for changes in error-related code

## Incident Timeline

### Building the Timeline

```yaml
incident_timeline:
  events:
    - timestamp: "2024-06-20T14:00:00Z"
      type: "deployment"
      description: "Deployed version 1.2.3"
      source: "CI/CD"

    - timestamp: "2024-06-20T14:05:00Z"
      type: "metric_change"
      description: "Error rate increased from 0.1% to 5%"
      source: "Datadog"

    - timestamp: "2024-06-20T14:06:00Z"
      type: "alert"
      description: "High Error Rate alert triggered"
      source: "Datadog"

    - timestamp: "2024-06-20T14:10:00Z"
      type: "incident_created"
      description: "SEV-1 incident created"
      source: "PagerDuty"

    - timestamp: "2024-06-20T14:15:00Z"
      type: "action"
      description: "Rolled back to version 1.2.2"
      source: "Engineer"

    - timestamp: "2024-06-20T14:20:00Z"
      type: "metric_change"
      description: "Error rate returned to 0.1%"
      source: "Datadog"

    - timestamp: "2024-06-20T14:25:00Z"
      type: "incident_resolved"
      description: "Incident marked resolved"
      source: "PagerDuty"
```

### Automated Timeline Generation

```csharp
public class TimelineBuilder
{
    public async Task<Timeline> BuildTimelineAsync(Incident incident)
    {
        var timeline = new Timeline();

        // Get alerts in window
        var alerts = await _datadogClient.GetAlertsAsync(
            incident.StartTime.AddHours(-1),
            incident.EndTime.AddHours(1),
            incident.AffectedServices
        );

        // Get deployments in window
        var deployments = await _datadogClient.GetEventsAsync(
            "sources:deployment",
            incident.StartTime.AddHours(-2),
            incident.StartTime
        );

        // Get metric changes (anomalies)
        var anomalies = await _datadogClient.GetAnomaliesAsync(
            incident.StartTime.AddMinutes(-30),
            incident.EndTime,
            incident.AffectedServices
        );

        // Get error logs
        var errorLogs = await _datadogClient.GetLogsAsync(
            $"service:{incident.PrimaryService} level:ERROR",
            incident.StartTime,
            incident.EndTime,
            limit: 100
        );

        timeline.AddEvents(alerts.Select(a => new TimelineEvent("alert", a)));
        timeline.AddEvents(deployments.Select(d => new TimelineEvent("deployment", d)));
        timeline.AddEvents(anomalies.Select(a => new TimelineEvent("anomaly", a)));
        timeline.AddEvents(GroupErrors(errorLogs));

        return timeline.OrderByTime();
    }
}
```

## Post-Incident Analysis

### Metrics to Capture

```yaml
postmortem_metrics:
  # Time to detect
  time_to_detect:
    start: "First anomaly or customer report"
    end: "Alert fired"
    target: "< 5 minutes"

  # Time to respond
  time_to_respond:
    start: "Alert fired"
    end: "Engineer acknowledged"
    target: "< 15 minutes"

  # Time to mitigate
  time_to_mitigate:
    start: "Engineer acknowledged"
    end: "Impact reduced"
    target: "< 30 minutes"

  # Time to resolve
  time_to_resolve:
    start: "Incident start"
    end: "Root cause fixed"
    target: "< 4 hours"

  # Impact
  impact:
    affected_users: "Count of users with errors"
    error_count: "Total errors during incident"
    revenue_impact: "Estimated revenue loss"
```

### Observability Improvements

After each incident, evaluate:

1. **Detection Gap**: Did we have the right alerts? Could we have detected earlier?
2. **Visibility Gap**: Did we have the right dashboards? Could we diagnose faster?
3. **Context Gap**: Did logs/traces have sufficient context?
4. **Correlation Gap**: Could we correlate across services effectively?

Add action items to backlog:
```yaml
observability_improvements:
  - type: "new_alert"
    description: "Add alert for database connection pool exhaustion"
    priority: "high"

  - type: "new_metric"
    description: "Add per-tenant error rate metric"
    priority: "medium"

  - type: "log_enhancement"
    description: "Add tenant_id to all payment service logs"
    priority: "high"

  - type: "dashboard_update"
    description: "Add database connection pool to order-api dashboard"
    priority: "medium"
```

---
[Back to Overview](./OVERVIEW.md)
