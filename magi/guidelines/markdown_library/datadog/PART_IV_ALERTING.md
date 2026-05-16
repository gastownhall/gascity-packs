# Part IV: Alerting Strategy

This section defines when and how to alert, minimizing noise while catching real issues.

## Alert Philosophy

### Only Alert on Actionable Conditions

Every alert must have:
1. **Clear meaning**: What is happening?
2. **Clear owner**: Who should respond?
3. **Clear action**: What should they do?
4. **Clear urgency**: When should they respond?

### Alert Severity Levels

| Severity     | Response Time       | Example                                           | Notification          |
|--------------|---------------------|---------------------------------------------------|-----------------------|
| **Critical** | Immediate (wake up) | Service down, data loss risk                      | PagerDuty, phone call |
| **High**     | Within 1 hour       | Degraded performance, error rate spike            | PagerDuty, Slack      |
| **Medium**   | Within 4 hours      | Elevated latency, capacity warning                | Slack, email          |
| **Low**      | Next business day   | Non-critical warnings, optimization opportunities | Email, dashboard      |

### Alert Anti-Patterns

**Alerting on Symptoms, Not Causes**:
```
# BAD: Alerts on individual pod restarts
# This could fire repeatedly during normal deployments

# GOOD: Alert on service availability impact
sum:kubernetes.containers.restarts{service:order-api}.rollup(sum, 300) > 5
AND
sum:http.requests.total{service:order-api,status_class:5xx} / sum:http.requests.total{service:order-api} > 0.01
```

**Over-Alerting**:
```
# BAD: Alert on any error
errors.total{service:order-api} > 0

# GOOD: Alert on error rate exceeding threshold
( sum:errors.total{service:order-api}.as_rate() /
  sum:requests.total{service:order-api}.as_rate() ) > 0.01
```

**Under-Alerting**:
```
# BAD: Only alert when service is completely down
availability = 0

# GOOD: Alert on SLO burn rate
error_budget_burn_rate > 14.4 over 1 hour
```

## Alert Types

### Threshold Alerts

Simple comparison against static value:

```yaml
name: "High Error Rate"
type: "metric_alert"
query: |
  ( sum:http.requests.total{service:order-api,status_class:5xx}.as_rate() /
    sum:http.requests.total{service:order-api}.as_rate() ) * 100
thresholds:
  critical: 5     # 5% error rate
  warning: 1      # 1% error rate
message: |
  Error rate for order-api is {{value}}%.
  {{#is_alert}}Investigate immediately.{{/is_alert}}
  {{#is_warning}}Monitor closely.{{/is_warning}}
```

### Anomaly Detection Alerts

Use Datadog's anomaly detection for metrics with variable baselines:

```yaml
name: "Unusual Traffic Pattern"
type: "metric_alert"
query: |
  avg(last_4h):anomalies(
    sum:http.requests.total{service:order-api}.as_rate(),
    'agile', 3
  ) >= 1
message: |
  Traffic to order-api is outside normal patterns.
  Current: {{value}} requests/sec
  Consider: scheduled job, marketing campaign, or potential attack.
```

### Change Alerts

Alert on significant changes compared to previous period:

```yaml
name: "Error Rate Increase"
type: "metric_alert"
query: |
  pct_change(sum:http.errors.total{service:order-api}.as_rate(), 1h) > 100
message: |
  Error rate has increased by {{value}}% compared to 1 hour ago.
  Investigate recent deployments or upstream changes.
```

### Composite Alerts

Combine multiple conditions:

```yaml
name: "Service Degradation"
type: "composite"
query: |
  ( $error_rate > 1 AND $latency_p99 > 500 )
  OR
  ( $error_rate > 5 )
variables:
  error_rate: |
    ( sum:http.requests.total{service:order-api,status_class:5xx}.as_rate() /
      sum:http.requests.total{service:order-api}.as_rate() ) * 100
  latency_p99: |
    p99:http.requests.duration_ms{service:order-api}
```

### SLO-Based Alerts

Alert on error budget consumption:

```yaml
name: "SLO Error Budget Alert"
type: "slo_alert"
slo_id: "order-api-availability"
alert_thresholds:
  # Fast burn: 2% of monthly budget in 1 hour = severe incident
  - burn_rate: 14.4
    window: "1h"
    severity: "critical"
  # Slow burn: 5% of monthly budget in 6 hours = gradual degradation
  - burn_rate: 6
    window: "6h"
    severity: "warning"
```

## Alert Routing

### Team-Based Routing

Route alerts to appropriate teams based on service ownership:

```yaml
# routing rules
rules:
  - match:
      service: order-api
      service: payment-service
    route:
      team: checkout-team
      pagerduty: checkout-team-pd
      slack: "#checkout-alerts"

  - match:
      service: user-service
      service: auth-service
    route:
      team: platform-team
      pagerduty: platform-pd
      slack: "#platform-alerts"

  - match:
      severity: critical
    route:
      pagerduty: primary-oncall
      slack: "#critical-alerts"
```

### Escalation Policies

Define escalation for unacknowledged alerts:

```yaml
escalation_policy:
  - name: "Standard Escalation"
    steps:
      - delay: 0
        targets:
          - primary_oncall
      - delay: 15m
        targets:
          - secondary_oncall
      - delay: 30m
        targets:
          - team_lead
      - delay: 1h
        targets:
          - engineering_manager
```

### Alert Suppression

Reduce noise during known events:

```yaml
# Suppress alerts during deployment
downtime:
  name: "Order API Deployment"
  scope: "service:order-api"
  start: "2024-06-20T14:00:00Z"
  end: "2024-06-20T14:30:00Z"
  message: "Planned deployment - expected brief downtime"

# Suppress dependent alerts when root cause is known
mute_rules:
  - condition: "service:database AND alert:connection_timeout"
    mute:
      - "service:order-api AND alert:high_latency"
      - "service:payment-service AND alert:high_latency"
```

## Alert Documentation

Every alert must have runbook documentation:

```yaml
name: "High Error Rate - Order API"
message: |
  ## Summary
  Order API error rate is {{value}}%, exceeding threshold of {{threshold}}%.

  ## Impact
  - Customers may be unable to place orders
  - Revenue impact: approximately $X per minute of outage

  ## Quick Diagnosis
  1. Check [Order API Dashboard](https://app.datadoghq.com/dashboard/abc123)
  2. Check [Recent Deployments](https://app.datadoghq.com/ci/pipelines)
  3. Check [Upstream Dependencies Status](https://status.example.com)

  ## Common Causes
  - Recent deployment introduced bug
  - Database connection pool exhaustion
  - Upstream payment service outage
  - Traffic spike from marketing campaign

  ## Remediation Steps
  1. If deployment related: Roll back via `kubectl rollout undo deployment/order-api`
  2. If database related: Check connection pool, restart pods if needed
  3. If upstream: Enable circuit breaker, switch to fallback

  ## Escalation
  If unresolved after 15 minutes, escalate to @checkout-team-lead

  ## Related Runbooks
  - [Order API Runbook](https://wiki.example.com/runbooks/order-api)
  - [Database Troubleshooting](https://wiki.example.com/runbooks/database)
```

---
[Back to Overview](./OVERVIEW.md)
