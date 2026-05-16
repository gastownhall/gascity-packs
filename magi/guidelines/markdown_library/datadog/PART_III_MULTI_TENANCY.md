# Part III: Multi-Tenancy Observability

This section addresses observability in multi-tenant environments, where understanding per-tenant behavior is critical.

## Tenant-Aware Instrumentation

### Mandatory Tenant Tagging

Every metric, log, and trace must include tenant identification when processing tenant-specific requests:

```csharp
public class TenantContextMiddleware
{
    public async Task InvokeAsync(HttpContext context)
    {
        var tenantId = ExtractTenantId(context);

        if (!string.IsNullOrEmpty(tenantId))
        {
            // Set on current activity for traces
            Activity.Current?.SetTag("tenant_id", tenantId);

            // Set in async local for logging
            TenantContext.Current = new TenantContext(tenantId);
        }

        await _next(context);
    }
}
```

### Per-Tenant Metrics

```csharp
public void RecordOrderPlaced(Order order)
{
    var tags = new[]
    {
        $"tenant_id:{order.TenantId}",
        $"tier:{GetTier(order.TenantId)}",
        $"service:order-service",
        $"env:{_environment}"
    };

    DogStatsd.Increment("business.orders.placed", tags: tags);
    DogStatsd.Distribution("business.orders.value", order.Total, tags: tags);
}
```

### Tenant Cardinality Management

With thousands of tenants, cardinality becomes a concern. Strategies:

**Tier-Based Aggregation**:
```csharp
// For metrics where per-tenant detail isn't critical
var tier = GetTenantTier(tenantId);  // Returns: "enterprise", "business", "free"
DogStatsd.Increment("api.requests", tags: new[] { $"tier:{tier}" });
```

**Top-N Tenants + Others**:
```csharp
// Track top tenants individually, aggregate rest
var topTenants = GetTopTenants();  // Pre-configured list of high-value tenants
var tagValue = topTenants.Contains(tenantId) ? tenantId : "other";
DogStatsd.Increment("api.requests", tags: new[] { $"tenant:{tagValue}" });
```

**Separate Metrics for High-Value Tenants**:
```csharp
// Detailed metrics only for enterprise tenants
if (IsEnterpriseTenant(tenantId))
{
    DogStatsd.Increment("enterprise.api.requests", tags: new[] { $"tenant_id:{tenantId}" });
}

// Aggregated metrics for all tenants
DogStatsd.Increment("api.requests", tags: new[] { $"tier:{tier}" });
```

## Tenant-Specific Dashboards

### Dashboard Variables

Configure dashboard variables for tenant selection:

```yaml
# Dashboard template variable
- name: tenant_id
  type: tag
  tag: tenant_id
  default: "*"
  filter: "service:order-api"
```

### Per-Tenant Widgets

**Request Rate by Tenant**:
```
sum:http.requests.total{service:order-api,$tenant_id} by {tenant_id}.as_rate()
```

**Latency by Tenant**:
```
p99:http.requests.duration_ms{service:order-api,$tenant_id} by {tenant_id}
```

**Error Rate by Tenant**:
```
( sum:http.requests.total{service:order-api,status_class:5xx,$tenant_id} by {tenant_id} /
  sum:http.requests.total{service:order-api,$tenant_id} by {tenant_id} ) * 100
```

### Tenant Health Scorecard

Build a composite health score per tenant:

```
# Tenant health score (0-100)
( (availability_score * 0.4) +
  (latency_score * 0.3) +
  (error_rate_score * 0.3) )

# Where:
# availability_score = (successful_requests / total_requests) * 100
# latency_score = 100 - min((p99_latency / target_latency) * 100, 100)
# error_rate_score = 100 - min((error_rate / threshold) * 100, 100)
```

## Noisy Neighbor Detection

### Identifying Resource-Heavy Tenants

**Request Volume**:
```
# Top 10 tenants by request volume
top(sum:http.requests.total{service:order-api} by {tenant_id}.as_rate(), 10, 'mean', 'desc')
```

**Resource Consumption**:
```
# CPU usage by tenant (requires custom instrumentation)
top(avg:app.cpu.usage{service:order-api} by {tenant_id}, 10, 'mean', 'desc')
```

**Database Load**:
```
# Query duration by tenant
top(sum:db.queries.duration_seconds{service:order-api} by {tenant_id}, 10, 'sum', 'desc')
```

### Alerting on Noisy Neighbors

```yaml
# Alert when single tenant exceeds 20% of total traffic
name: "Noisy Neighbor Alert"
type: "query_alert"
query: |
  ( sum:http.requests.total{service:order-api} by {tenant_id}.as_rate() /
    sum:http.requests.total{service:order-api}.as_rate() ) * 100
threshold: 20
comparison: ">"
message: |
  Tenant {{tenant_id.name}} is consuming {{value}}% of total traffic.
  Investigate for potential abuse or need for rate limiting.
```

### Rate Limiting Integration

Emit metrics for rate limiting decisions:

```csharp
public class RateLimitMiddleware
{
    public async Task InvokeAsync(HttpContext context)
    {
        var tenantId = GetTenantId(context);
        var allowed = await _rateLimiter.CheckAsync(tenantId);

        var tags = new[] { $"tenant_id:{tenantId}", $"allowed:{allowed}" };
        DogStatsd.Increment("ratelimit.checks", tags: tags);

        if (!allowed)
        {
            DogStatsd.Increment("ratelimit.rejected", tags: tags);
            context.Response.StatusCode = 429;
            return;
        }

        await _next(context);
    }
}
```

## Tenant Isolation Verification

### Cross-Tenant Monitoring

Ensure tenants cannot access each other's data:

```csharp
public class TenantIsolationAuditor
{
    public void AuditDataAccess(string requestingTenantId, string dataOwnerId, string resourceType)
    {
        if (requestingTenantId != dataOwnerId)
        {
            // Log security event
            _logger.LogWarning(
                "Cross-tenant data access detected. Requester: {Requester}, Owner: {Owner}, Resource: {Resource}",
                requestingTenantId, dataOwnerId, resourceType
            );

            // Emit metric
            DogStatsd.Increment("security.cross_tenant_access", tags: new[]
            {
                $"requester:{requestingTenantId}",
                $"owner:{dataOwnerId}",
                $"resource:{resourceType}"
            });
        }
    }
}
```

### Audit Dashboard

Track tenant isolation metrics:
- Cross-tenant access attempts (should be zero)
- Tenant context propagation failures
- Authorization denial rates by tenant

---
[Back to Overview](./OVERVIEW.md)
