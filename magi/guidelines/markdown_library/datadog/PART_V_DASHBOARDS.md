# Part V: Dashboards and Visualization

This section provides guidance on building effective dashboards.

## Dashboard Hierarchy

### Level 1: Executive Overview

High-level business health, updated every few minutes:
- Overall system availability
- Key business metrics (orders, revenue, active users)
- SLO compliance summary
- Major incident status

**Audience**: Executives, stakeholders, status pages

### Level 2: Service Overview

Service-level health for each major service:
- Request rate, error rate, latency
- Resource utilization
- Dependency health
- Recent deployments

**Audience**: On-call engineers, service owners

### Level 3: Detailed Debugging

Deep-dive dashboards for troubleshooting:
- Per-endpoint metrics
- Database query performance
- Cache hit rates
- Trace analysis

**Audience**: Engineers actively debugging

### Level 4: Capacity Planning

Resource trends and forecasting:
- Historical resource usage
- Growth trends
- Capacity projections
- Cost analysis

**Audience**: Platform team, capacity planners

## Dashboard Design Principles

### Golden Signals Dashboard

Every service should have a dashboard covering the four golden signals:

**Latency**:
```
# p50, p90, p99 latency over time
p50:http.requests.duration_ms{service:order-api}
p90:http.requests.duration_ms{service:order-api}
p99:http.requests.duration_ms{service:order-api}
```

**Traffic**:
```
# Requests per second
sum:http.requests.total{service:order-api}.as_rate()
```

**Errors**:
```
# Error rate percentage
( sum:http.requests.total{service:order-api,status_class:5xx}.as_rate() /
  sum:http.requests.total{service:order-api}.as_rate() ) * 100
```

**Saturation**:
```
# CPU utilization
avg:system.cpu.user{service:order-api}

# Memory utilization
avg:system.mem.used{service:order-api} / avg:system.mem.total{service:order-api} * 100

# Connection pool utilization
avg:db.connections.active{service:order-api} / avg:db.connections.max{service:order-api} * 100
```

### RED Method Dashboard

Request-focused metrics:

**Rate**:
```
sum:http.requests.total{service:order-api} by {endpoint}.as_rate()
```

**Errors**:
```
sum:http.requests.total{service:order-api,status_class:5xx} by {endpoint}.as_rate()
```

**Duration**:
```
p99:http.requests.duration_ms{service:order-api} by {endpoint}
```

### USE Method Dashboard

Resource-focused metrics:

**Utilization**:
```
# CPU utilization
avg:system.cpu.user{host:*} by {host}

# Memory utilization
avg:system.mem.used{host:*} / avg:system.mem.total{host:*} * 100

# Disk utilization
avg:system.disk.used{host:*} / avg:system.disk.total{host:*} * 100
```

**Saturation**:
```
# CPU run queue
avg:system.load.1{host:*}

# Disk I/O queue
avg:system.io.await{host:*}

# Network dropped packets
sum:system.net.packets_out.error{host:*}
```

**Errors**:
```
# Disk errors
sum:system.disk.errors{host:*}

# Network errors
sum:system.net.errors{host:*}
```

## Dashboard Templates

### Service Health Dashboard Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    Service: order-api                           │
│  Version: 1.2.3 | Last Deploy: 2h ago | SLO: 99.92%            │
├─────────────────────────────────────────────────────────────────┤
│ Request Rate     │ Error Rate       │ p99 Latency   │ Availability│
│ [graph]          │ [graph]          │ [graph]       │ [99.92%]   │
├─────────────────────────────────────────────────────────────────┤
│ Errors by Type                      │ Latency by Endpoint       │
│ [top list]                          │ [heatmap]                 │
├─────────────────────────────────────────────────────────────────┤
│ Resource Utilization                                            │
│ CPU [gauge] | Memory [gauge] | Connections [gauge] | Pods [n/m] │
├─────────────────────────────────────────────────────────────────┤
│ Dependencies                                                    │
│ [payment-api: OK] [database: OK] [redis: OK] [queue: OK]       │
├─────────────────────────────────────────────────────────────────┤
│ Recent Logs (Errors)               │ Active Traces              │
│ [log stream]                       │ [trace list]               │
└─────────────────────────────────────────────────────────────────┘
```

### Business Dashboard Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    Business Overview                             │
│  Period: Last 24 hours | Timezone: UTC                          │
├─────────────────────────────────────────────────────────────────┤
│ Orders/Hour      │ Revenue/Hour     │ Active Users  │ Conversion │
│ [1,234]          │ [$45,678]        │ [12,345]      │ [3.2%]     │
├─────────────────────────────────────────────────────────────────┤
│ Orders Over Time                    │ Revenue by Region          │
│ [timeseries graph]                  │ [bar chart]                │
├─────────────────────────────────────────────────────────────────┤
│ Top Products                        │ Top Tenants                │
│ [top list]                          │ [top list]                 │
├─────────────────────────────────────────────────────────────────┤
│ Funnel Analysis                                                 │
│ Visit → Browse → Cart → Checkout → Purchase                    │
│ [funnel visualization]                                          │
└─────────────────────────────────────────────────────────────────┘
```

## Visualization Best Practices

### Choosing Chart Types

| Data Type                     | Chart Type    | When to Use                   |
|-------------------------------|---------------|-------------------------------|
| Time series, single metric    | Line chart    | Showing trends over time      |
| Time series, multiple metrics | Stacked area  | Showing composition over time |
| Current values                | Gauge/Number  | Showing current state         |
| Comparison                    | Bar chart     | Comparing discrete categories |
| Distribution                  | Heatmap       | Showing latency distribution  |
| Top N                         | Top list      | Showing highest values        |
| Status                        | Status widget | Showing up/down state         |
| Correlation                   | Scatter plot  | Finding relationships         |

### Color Conventions

| Color  | Meaning          | Usage                   |
|--------|------------------|-------------------------|
| Green  | Healthy/Good     | SLO met, low error rate |
| Yellow | Warning          | Approaching threshold   |
| Red    | Critical/Bad     | SLO breach, high errors |
| Blue   | Informational    | Neutral metrics         |
| Gray   | Disabled/Unknown | Missing data            |

### Time Window Guidelines

| Use Case             | Time Window                        |
|----------------------|------------------------------------|
| Active incident      | Last 15 minutes - 1 hour           |
| Daily operations     | Last 1-4 hours                     |
| Trend analysis       | Last 24 hours - 7 days             |
| Capacity planning    | Last 30-90 days                    |
| Post-incident review | Custom (incident window + context) |

---
[Back to Overview](./OVERVIEW.md)
