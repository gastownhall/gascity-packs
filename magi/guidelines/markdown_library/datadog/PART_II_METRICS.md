# Part II: Metrics Deep Dive

This section provides detailed guidance on metric collection, naming, and usage patterns.

## Metric Types

### Counter

**What It Is**: Monotonically increasing value, reset on restart.

**When to Use**: Counting occurrences of events.

```csharp
// Requests received
DogStatsd.Increment("http.requests.total", tags: new[] { "endpoint:/api/orders", "method:POST" });

// Orders placed
DogStatsd.Increment("business.orders.placed", tags: new[] { "tenant_id:acme", "tier:enterprise" });

// Errors encountered
DogStatsd.Increment("errors.total", tags: new[] { "error_type:ValidationError", "service:order-api" });
```

**Query Patterns**:
```
# Rate of requests per second
rate(http.requests.total{service:order-api}) by {endpoint}

# Total errors in last hour
sum(errors.total{service:order-api}).rollup(sum, 3600)
```

### Gauge

**What It Is**: Point-in-time value that can go up or down.

**When to Use**: Current state measurements.

```csharp
// Current queue depth
DogStatsd.Gauge("queue.depth", queueLength, tags: new[] { "queue:orders" });

// Active connections
DogStatsd.Gauge("connections.active", connectionCount, tags: new[] { "pool:database" });

// Memory usage
DogStatsd.Gauge("process.memory.used_bytes", memoryBytes, tags: new[] { "service:order-api" });
```

**Query Patterns**:
```
# Average queue depth over time
avg(queue.depth{queue:orders})

# Max connections in last hour
max(connections.active{pool:database}).rollup(max, 3600)
```

### Histogram/Distribution

**What It Is**: Statistical distribution of values (count, sum, min, max, percentiles).

**When to Use**: Latency, size, duration measurements.

```csharp
// Request latency
DogStatsd.Distribution("http.request.duration", latencyMs, tags: new[] { "endpoint:/api/orders" });

// Payload size
DogStatsd.Distribution("http.request.size_bytes", requestSize, tags: new[] { "endpoint:/api/orders" });

// Processing time
DogStatsd.Distribution("order.processing_time_ms", processingTime, tags: new[] { "tenant_id:acme" });
```

**Query Patterns**:
```
# p99 latency
p99(http.request.duration{service:order-api}) by {endpoint}

# Average latency
avg(http.request.duration{service:order-api}) by {endpoint}

# Latency percentiles
percentile(http.request.duration{service:order-api}, 50, 90, 95, 99)
```

### Set

**What It Is**: Count of unique values.

**When to Use**: Counting unique items (users, sessions, IPs).

```csharp
// Unique users
DogStatsd.Set("users.unique", userId, tags: new[] { "service:web-app" });

// Unique IP addresses
DogStatsd.Set("requests.unique_ips", ipAddress, tags: new[] { "endpoint:/api/orders" });
```

## Metric Naming Conventions

### Naming Structure

```
<namespace>.<entity>.<attribute>[.<unit>]
```

**Components**:
- `namespace`: Domain or subsystem (`http`, `db`, `queue`, `business`, `custom`)
- `entity`: What is being measured (`requests`, `orders`, `connections`)
- `attribute`: What aspect is measured (`count`, `duration`, `size`)
- `unit`: Optional unit suffix (`_bytes`, `_seconds`, `_percent`)

### Standard Metric Names

**HTTP Metrics**:
```
http.requests.total              # Counter: total requests
http.requests.duration_seconds   # Distribution: request latency
http.requests.size_bytes         # Distribution: request size
http.responses.size_bytes        # Distribution: response size
http.errors.total                # Counter: HTTP errors
```

**Database Metrics**:
```
db.connections.active            # Gauge: active connections
db.connections.idle              # Gauge: idle connections
db.connections.wait_time_seconds # Distribution: connection wait time
db.queries.total                 # Counter: queries executed
db.queries.duration_seconds      # Distribution: query latency
db.queries.rows_affected         # Distribution: rows affected
```

**Queue Metrics**:
```
queue.messages.published         # Counter: messages sent
queue.messages.consumed          # Counter: messages processed
queue.messages.failed            # Counter: processing failures
queue.depth                      # Gauge: pending messages
queue.processing_time_seconds    # Distribution: processing duration
```

**Business Metrics**:
```
business.orders.placed           # Counter: orders created
business.orders.value_dollars    # Distribution: order value
business.payments.processed      # Counter: successful payments
business.payments.failed         # Counter: payment failures
business.users.registered        # Counter: new registrations
business.users.active            # Gauge: active users
```

**Cache Metrics**:
```
cache.hits                       # Counter: cache hits
cache.misses                     # Counter: cache misses
cache.size_bytes                 # Gauge: cache size
cache.evictions                  # Counter: items evicted
cache.latency_seconds            # Distribution: operation latency
```

### Anti-Patterns

```
# BAD: No namespace
requests_total                   # Use http.requests.total

# BAD: Inconsistent naming
httpRequestCount                 # Use http.requests.total
HTTP_REQUESTS                    # Use http.requests.total

# BAD: Including dynamic data in name
order_12345_processing_time      # Use tags for order_id

# BAD: Unit not specified
request_latency                  # Use request_latency_seconds or _ms

# BAD: Verb in name
measure_cpu_usage                # Use system.cpu.usage
```

## Custom Metrics Best Practices

### Instrumentation Code Patterns

**Request/Response Instrumentation**:
```csharp
public class MetricsMiddleware
{
    private readonly RequestDelegate _next;

    public async Task InvokeAsync(HttpContext context)
    {
        var stopwatch = Stopwatch.StartNew();
        var tags = new List<string>
        {
            $"service:{_serviceName}",
            $"env:{_environment}",
            $"method:{context.Request.Method}",
            $"endpoint:{NormalizeEndpoint(context.Request.Path)}"
        };

        try
        {
            await _next(context);

            tags.Add($"status_code:{context.Response.StatusCode}");
            tags.Add($"status_class:{context.Response.StatusCode / 100}xx");
        }
        catch (Exception ex)
        {
            tags.Add("status_code:500");
            tags.Add("status_class:5xx");
            tags.Add($"error_type:{ex.GetType().Name}");
            throw;
        }
        finally
        {
            stopwatch.Stop();

            DogStatsd.Increment("http.requests.total", tags: tags.ToArray());
            DogStatsd.Distribution("http.requests.duration_ms", stopwatch.ElapsedMilliseconds, tags: tags.ToArray());
        }
    }

    private static string NormalizeEndpoint(PathString path)
    {
        // Normalize /api/orders/123 to /api/orders/{id}
        // Prevents high cardinality from dynamic path segments
        return PathNormalizer.Normalize(path.Value);
    }
}
```

**Business Event Instrumentation**:
```csharp
public class OrderService
{
    public async Task<Order> CreateOrderAsync(CreateOrderRequest request, CancellationToken ct)
    {
        var stopwatch = Stopwatch.StartNew();
        var tags = new[]
        {
            $"tenant_id:{request.TenantId}",
            $"tier:{GetTenantTier(request.TenantId)}",
            $"service:order-service",
            $"env:{_environment}"
        };

        try
        {
            var order = await ProcessOrderAsync(request, ct);

            stopwatch.Stop();

            // Business metrics
            DogStatsd.Increment("business.orders.placed", tags: tags);
            DogStatsd.Distribution("business.orders.value", order.TotalAmount, tags: tags);
            DogStatsd.Distribution("business.orders.item_count", order.Items.Count, tags: tags);
            DogStatsd.Distribution("business.orders.processing_time_ms", stopwatch.ElapsedMilliseconds, tags: tags);

            return order;
        }
        catch (Exception ex)
        {
            DogStatsd.Increment("business.orders.failed", tags: tags.Append($"error_type:{ex.GetType().Name}").ToArray());
            throw;
        }
    }
}
```

**External Dependency Instrumentation**:
```csharp
public class InstrumentedHttpClient
{
    private readonly HttpClient _httpClient;

    public async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct)
    {
        var stopwatch = Stopwatch.StartNew();
        var targetService = ExtractServiceName(request.RequestUri);
        var tags = new List<string>
        {
            $"calling_service:{_serviceName}",
            $"target_service:{targetService}",
            $"method:{request.Method}",
            $"env:{_environment}"
        };

        try
        {
            var response = await _httpClient.SendAsync(request, ct);
            stopwatch.Stop();

            tags.Add($"status_code:{(int)response.StatusCode}");
            DogStatsd.Distribution("http.client.duration_ms", stopwatch.ElapsedMilliseconds, tags: tags.ToArray());
            DogStatsd.Increment("http.client.requests", tags: tags.ToArray());

            return response;
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            tags.Add($"error_type:{ex.GetType().Name}");
            DogStatsd.Distribution("http.client.duration_ms", stopwatch.ElapsedMilliseconds, tags: tags.ToArray());
            DogStatsd.Increment("http.client.errors", tags: tags.ToArray());
            throw;
        }
    }
}
```

## SLIs, SLOs, and SLAs

### Definitions

- **SLI (Service Level Indicator)**: A quantitative measure of service behavior (latency, error rate, throughput)
- **SLO (Service Level Objective)**: A target value for an SLI (99.9% availability, p99 < 200ms)
- **SLA (Service Level Agreement)**: A contractual commitment to meet SLOs with consequences for breach

### Defining SLIs

**Availability SLI**:
```
availability = successful_requests / total_requests
```

```
# Datadog query
( sum(http.requests.total{service:order-api,status_class:2xx}) /
  sum(http.requests.total{service:order-api}) ) * 100
```

**Latency SLI**:
```
latency_sli = requests_below_threshold / total_requests
```

```
# Percentage of requests under 200ms
( count_values(http.requests.duration_ms{service:order-api}, lt, 200) /
  count(http.requests.duration_ms{service:order-api}) ) * 100
```

**Error Rate SLI**:
```
error_rate = failed_requests / total_requests
```

```
# Error rate percentage
( sum(http.requests.total{service:order-api,status_class:5xx}) /
  sum(http.requests.total{service:order-api}) ) * 100
```

### Implementing SLOs in Datadog

**SLO Definition**:
```yaml
# Order API Availability SLO
name: "Order API Availability"
type: "metric"
description: "99.9% of requests should succeed"
target: 99.9
timeframe: "30d"
query:
  numerator: "sum:http.requests.total{service:order-api,status_class:2xx}.as_count()"
  denominator: "sum:http.requests.total{service:order-api}.as_count()"
```

**SLO Alerting**:
```yaml
# Alert when burning error budget too fast
name: "Order API Error Budget Alert"
type: "slo_burn_rate"
slo_id: "abc123"
alert_thresholds:
  - burn_rate: 14.4  # 1 hour: 2% budget burn
    window: "1h"
    severity: "critical"
  - burn_rate: 6.0   # 6 hours: 5% budget burn
    window: "6h"
    severity: "warning"
```

### Common SLO Targets

| Service Type       | Availability | Latency (p99) | Error Rate |
|--------------------|--------------|---------------|------------|
| Public API         | 99.9%        | < 500ms       | < 0.1%     |
| Internal API       | 99.5%        | < 200ms       | < 0.5%     |
| Batch Processing   | 99%          | N/A           | < 1%       |
| Background Jobs    | 95%          | N/A           | < 5%       |
| Payment Processing | 99.99%       | < 1s          | < 0.01%    |

### Error Budget Calculation

```
error_budget = 100% - slo_target
monthly_budget_minutes = 30 * 24 * 60 * (error_budget / 100)

# Example: 99.9% availability SLO
error_budget = 0.1%
monthly_budget_minutes = 30 * 24 * 60 * 0.001 = 43.2 minutes
```

---
[Back to Overview](./OVERVIEW.md)
