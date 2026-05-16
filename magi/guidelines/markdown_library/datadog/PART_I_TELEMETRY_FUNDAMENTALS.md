# Part I: Telemetry Fundamentals

This section covers the three pillars of observability: metrics, logs, and traces. Understanding when and how to use each is foundational.

## The Three Pillars

### Metrics

**What They Are**: Numeric measurements aggregated over time. Counters, gauges, histograms, and distributions.

**Strengths**:
- Highly efficient storage (pre-aggregated)
- Fast query performance
- Excellent for dashboards and alerts
- Low cost per data point

**Weaknesses**:
- No individual event detail
- Cardinality limits constrain dimensionality
- Cannot reconstruct specific transactions

**Use For**:
- System health indicators (CPU, memory, disk, network)
- Business KPIs (orders/minute, revenue, active users)
- SLI/SLO tracking
- Alerting thresholds
- Capacity planning

### Logs

**What They Are**: Discrete, timestamped text records of events.

**Strengths**:
- Rich contextual detail
- Human-readable for debugging
- Can contain arbitrary structured data
- Searchable and filterable

**Weaknesses**:
- High storage cost at scale
- Query performance degrades with volume
- Easy to over-log, creating noise

**Use For**:
- Error details and stack traces
- Audit trails
- Security events
- Debug information (with appropriate log levels)
- Business event records

### Traces

**What They Are**: Records of request flow across distributed services, composed of spans.

**Strengths**:
- Visualize request path across services
- Identify latency bottlenecks
- Understand service dependencies
- Correlate errors across service boundaries

**Weaknesses**:
- Highest storage cost per transaction
- Requires instrumentation across all services
- Sampling necessary at scale

**Use For**:
- Debugging distributed system issues
- Performance optimization
- Understanding service dependencies
- Root cause analysis for latency problems

### Choosing the Right Telemetry Type

| Question                                 | Best Telemetry           |
|------------------------------------------|--------------------------|
| How many requests per second?            | Metric (counter)         |
| What is the p99 latency?                 | Metric (distribution)    |
| Why did this specific request fail?      | Trace + Logs             |
| How much memory is the service using?    | Metric (gauge)           |
| What SQL query caused the timeout?       | Trace span + Log         |
| How many unique users today?             | Metric (set/HyperLogLog) |
| What were the request parameters?        | Log (structured)         |
| Which downstream service caused latency? | Trace                    |

## Tagging Strategy

Tags are the foundation of observability context. A consistent tagging strategy is mandatory.

### Required Tags for All Telemetry

Every metric, log, and trace must include these tags:

| Tag       | Description        | Example                        |
|-----------|--------------------|--------------------------------|
| `env`     | Environment        | `prod`, `staging`, `dev`       |
| `service` | Service name       | `order-api`, `payment-service` |
| `version` | Deployment version | `1.2.3`, `abc123`              |
| `team`    | Owning team        | `checkout`, `platform`         |
| `region`  | Geographic region  | `eastus`, `westeurope`         |

### Recommended Tags by Telemetry Type

**Infrastructure Metrics**:
| Tag | Description | Example |
|----|------------|--------|
| `host` | Hostname/instance | `order-api-prod-001` |
| `container_id` | Container identifier | `abc123def` |
| `pod_name` | Kubernetes pod | `order-api-7d8f9-xyz` |
| `namespace` | Kubernetes namespace | `production` |
| `cluster` | Kubernetes cluster | `prod-eastus-1` |
| `availability_zone` | Cloud AZ | `eastus-1a` |

**Application Metrics**:
| Tag | Description | Example |
|----|------------|--------|
| `endpoint` | API endpoint | `/api/v2/orders` |
| `method` | HTTP method | `GET`, `POST` |
| `status_code` | Response status | `200`, `500` |
| `tenant_id` | Customer/tenant | `acme-corp` |
| `tier` | Customer tier | `enterprise`, `free` |
| `feature_flag` | Active feature flags | `new-checkout:enabled` |

**Logs**:
| Tag | Description | Example |
|----|------------|--------|
| `level` | Log level | `ERROR`, `WARN`, `INFO` |
| `logger` | Logger name | `OrderService` |
| `correlation_id` | Request correlation | `req-abc123` |
| `trace_id` | Trace identifier | `abc123def456` |
| `span_id` | Span identifier | `span-789` |
| `user_id` | User identifier | `user-456` (if permitted) |

**Traces**:
| Tag | Description | Example |
|----|------------|--------|
| `resource_name` | Operation name | `OrderController.CreateOrder` |
| `span.kind` | Span type | `server`, `client`, `internal` |
| `db.system` | Database type | `postgresql`, `redis` |
| `db.statement` | Query (sanitized) | `SELECT * FROM orders WHERE id = ?` |
| `http.url` | Request URL | `https://api.example.com/orders` |
| `error` | Error flag | `true` |
| `error.message` | Error description | `Connection refused` |

### Tag Naming Conventions

- **Format**: `snake_case` for custom tags
- **Prefix**: Use namespaces for custom tags: `app.`, `business.`, `custom.`
- **Values**: Lowercase, alphanumeric with hyphens: `order-api`, `prod-eastus`
- **Avoid**: Spaces, special characters, unbounded values (timestamps, UUIDs as tag values)

### Cardinality Management

Cardinality is the number of unique tag value combinations. High cardinality causes:
- Increased storage costs
- Slower query performance
- Potential metric rejection

**High-Cardinality Anti-Patterns**:
```
# NEVER DO THIS
metric.tag("user_id", userId)           # Millions of unique users
metric.tag("request_id", requestId)     # Unique per request
metric.tag("timestamp", timestamp)      # Infinite cardinality
metric.tag("session_id", sessionId)     # Unique per session
metric.tag("order_id", orderId)         # Unique per order
```

**Acceptable Cardinality**:
```
# ACCEPTABLE
metric.tag("tenant_id", tenantId)       # Hundreds to thousands
metric.tag("endpoint", endpoint)        # Tens to hundreds
metric.tag("status_code", statusCode)   # ~50 possible values
metric.tag("region", region)            # Single digits
metric.tag("tier", customerTier)        # 3-5 values
```

**Cardinality Guidelines**:
- Total unique combinations per metric: < 10,000
- Individual tag values: < 1,000 unique values preferred
- Monitor cardinality in Datadog Metrics Summary
- Use metric tags for filtering, not identification

## Structured Logging

### Log Format Standard

All logs must be structured JSON with consistent field names:

```json
{
  "timestamp": "2024-06-20T14:30:45.123Z",
  "level": "ERROR",
  "service": "order-api",
  "env": "prod",
  "version": "1.2.3",
  "host": "order-api-prod-001",
  "logger": "OrderService",
  "message": "\nFailed to process order",
  "trace_id": "abc123def456",
  "span_id": "span-789",
  "correlation_id": "req-abc123",
  "tenant_id": "acme-corp",
  "error": {
    "type": "PaymentDeclinedException",
    "message": "\nCard declined: insufficient funds",
    "stack_trace": "..."
  },
  "context": {
    "order_id": "order-456",
    "amount": 150.00,
    "currency": "USD"
  }
}
```

### Required Log Fields

Every log entry must include:
- `timestamp`: ISO 8601 format with timezone
- `level`: Log level (ERROR, WARN, INFO, DEBUG, TRACE)
- `service`: Service name
- `env`: Environment
- `message`: Human-readable description
- `trace_id`: Distributed trace identifier (when in request context)

### Log Levels and When to Use Them

| Level     | When to Use                             | Examples                                                         |
|-----------|-----------------------------------------|------------------------------------------------------------------|
| **ERROR** | Unexpected failures requiring attention | Unhandled exceptions, external service failures, data corruption |
| **WARN**  | Degraded operation, recoverable issues  | Retry succeeded, fallback used, deprecated API called            |
| **INFO**  | Significant business events             | Order created, user registered, payment processed                |
| **DEBUG** | Detailed diagnostic information         | Method entry/exit, intermediate values, decision points          |
| **TRACE** | Extremely detailed debugging            | Loop iterations, field-level changes, protocol details           |

### What to Log

**Always Log**:
- Request entry (INFO): Method, endpoint, tenant, correlation ID
- Request exit (INFO): Status code, duration, outcome
- Errors (ERROR): Full exception with stack trace, context
- Business events (INFO): Order placed, payment processed, user action
- Security events (WARN/ERROR): Authentication failures, authorization denials
- External calls (DEBUG): Service called, duration, response status

**Never Log**:
- Passwords, tokens, API keys, secrets
- Full credit card numbers (log last 4 only if needed)
- Personal health information (PHI)
- Personally identifiable information (PII) without explicit consent
- Large payloads (log size/hash instead)
- High-frequency events at INFO level (use DEBUG or metrics)

### Log Sampling

For high-volume services, implement log sampling to control costs:

```csharp
public class SampledLogger
{
    private readonly ILogger _logger;
    private readonly double _sampleRate;
    private readonly Random _random = new();

    public void LogDebug(string message, params object[] args)
    {
        if (_random.NextDouble() < _sampleRate)
        {
            _logger.LogDebug(message, args);
        }
    }
}
```

Sampling strategies:
- **Rate-based**: Log 10% of DEBUG messages
- **Error-biased**: Always log errors, sample success
- **Tenant-based**: Full logging for premium tenants, sampled for others
- **Endpoint-based**: Full logging for critical endpoints, sampled for health checks

### Log Retention Tiers

| Log Type | Retention | Rationale                           |
|----------|-----------|-------------------------------------|
| ERROR    | 90 days   | Root cause analysis, trend analysis |
| WARN     | 30 days   | Investigate degradation patterns    |
| INFO     | 15 days   | Audit, debugging recent issues      |
| DEBUG    | 3-7 days  | Active debugging only               |
| TRACE    | 1-3 days  | Active development/debugging        |

Configure Datadog log indexes with appropriate retention and filters.

## Distributed Tracing

### Trace Context Propagation

Every service must propagate trace context through all communication channels:

**HTTP Headers**:
```
x-datadog-trace-id: 1234567890
x-datadog-parent-id: 9876543210
x-datadog-sampling-priority: 1
x-datadog-origin: rum
```

**Message Queue Metadata**:
```json
{
  "dd-trace-id": "1234567890",
  "dd-parent-id": "9876543210",
  "dd-sampling-priority": "1"
}
```

### Span Best Practices

**Naming Conventions**:
- Use format: `ClassName.MethodName` or `resource.operation`
- Keep names stable (no dynamic content like IDs)
- Use resource name for the specific operation

```csharp
// GOOD
using var span = tracer.StartSpan("OrderService.CreateOrder");
span.SetTag("order_id", orderId);

// BAD
using var span = tracer.StartSpan($"CreateOrder_{orderId}"); // Dynamic name
```

**Required Span Tags**:
```csharp
span.SetTag("tenant_id", tenantId);
span.SetTag("user_id", userId);
span.SetTag("resource_name", "CreateOrder");
span.SetTag("component", "order-service");
```

**Error Recording**:
```csharp
catch (Exception ex)
{
    span.SetTag("error", true);
    span.SetTag("error.type", ex.GetType().Name);
    span.SetTag("error.message", ex.Message);
    span.SetTag("error.stack", ex.StackTrace);
    throw;
}
```

### Trace Sampling Strategy

At scale, 100% trace collection is cost-prohibitive. Implement intelligent sampling:

**Head-Based Sampling**:
- Decision made at trace start
- Consistent across all spans in trace
- Simple but may miss errors

**Tail-Based Sampling** (Preferred):
- Decision made after trace completes
- Keep all traces with errors
- Keep traces with high latency
- Sample successful, fast traces

**Recommended Sampling Rules**:
```yaml
# datadog-agent sampling config
apm_config:
  max_traces_per_second: 1000

  # Keep all error traces
  - service: "*"
    sample_rate: 1.0
    condition: "error:true"

  # Keep all slow traces
  - service: "*"
    sample_rate: 1.0
    condition: "duration:>5s"

  # Keep all traces for critical endpoints
  - service: "payment-service"
    resource: "ProcessPayment"
    sample_rate: 1.0

  # Sample routine operations
  - service: "*"
    resource: "HealthCheck"
    sample_rate: 0.01  # 1%

  # Default sampling for everything else
  - service: "*"
    sample_rate: 0.1  # 10%
```

### Correlating Traces, Logs, and Metrics

Ensure all telemetry can be correlated:

**Log to Trace Correlation**:
```csharp
public void ProcessOrder(Order order)
{
    var span = Tracer.ActiveSpan;
    _logger.LogInformation(
        "Processing order {OrderId} for tenant {TenantId}. TraceId: {TraceId}",
        order.Id,
        order.TenantId,
        span?.TraceId.ToString() ?? "no-trace"
    );
}
```

**Metric to Trace Correlation**:
```csharp
var tags = new[]
{
    $"trace_id:{span.TraceId}",
    $"service:{serviceName}",
    $"operation:{operationName}"
};
DogStatsd.Histogram("order.processing_time", duration, tags: tags);
```

---
[Back to Overview](./OVERVIEW.md)
