# Part IX: Integration Patterns

This section covers integrating Datadog with other systems.

## CI/CD Integration

### Deployment Tracking

Send deployment events to Datadog:

```yaml
# GitHub Actions example
- name: Send deployment event to Datadog
  run: |
    curl -X POST "https://api.datadoghq.com/api/v1/events" \
      -H "Content-Type: application/json" \
      -H "DD-API-KEY: ${{ secrets.DATADOG_API_KEY }}" \
      -d '{
        "title": "Deployment: ${{ github.repository }}",
        "text": "Deployed ${{ github.sha }} to ${{ env.ENVIRONMENT }}",
        "tags": [
          "service:${{ env.SERVICE_NAME }}",
          "env:${{ env.ENVIRONMENT }}",
          "version:${{ github.sha }}",
          "deployer:${{ github.actor }}"
        ],
        "alert_type": "info",
        "source_type_name": "deployment"
      }'
```

### Test Results

Send test results as metrics:

```yaml
- name: Report test results
  run: |
    # Parse test results
    PASSED=$(jq '.passed' test-results.json)
    FAILED=$(jq '.failed' test-results.json)
    DURATION=$(jq '.duration' test-results.json)

    # Send to Datadog
    echo "ci.tests.passed:$PASSED|g|#service:$SERVICE,env:ci" | nc -u -w1 localhost 8125
    echo "ci.tests.failed:$FAILED|g|#service:$SERVICE,env:ci" | nc -u -w1 localhost 8125
    echo "ci.tests.duration:$DURATION|g|#service:$SERVICE,env:ci" | nc -u -w1 localhost 8125
```

### Pipeline Metrics

Track CI/CD pipeline performance:

```yaml
metrics:
  - name: "ci.pipeline.duration"
    type: "distribution"
    tags: ["pipeline", "branch", "status"]

  - name: "ci.pipeline.success_rate"
    type: "gauge"
    calculation: "success_count / total_count"

  - name: "ci.deployment.frequency"
    type: "counter"
    tags: ["service", "environment"]
```

## APM Integration

### Automatic Instrumentation

Configure automatic instrumentation:

```yaml
# .NET
DD_TRACE_ENABLED: "true"
DD_SERVICE: "order-api"
DD_ENV: "prod"
DD_VERSION: "1.2.3"
DD_LOGS_INJECTION: "true"
DD_TRACE_SAMPLE_RATE: "1.0"
DD_RUNTIME_METRICS_ENABLED: "true"

# Additional integrations
DD_TRACE_ASPNET_ENABLED: "true"
DD_TRACE_SQL_ENABLED: "true"
DD_TRACE_REDIS_ENABLED: "true"
DD_TRACE_HTTP_ENABLED: "true"
```

### Custom Spans

Add custom spans for business operations:

```csharp
using Datadog.Trace;

public async Task<Order> ProcessOrderAsync(OrderRequest request)
{
    using var scope = Tracer.Instance.StartActive("ProcessOrder");
    var span = scope.Span;

    span.SetTag("tenant_id", request.TenantId);
    span.SetTag("order_type", request.Type.ToString());

    try
    {
        using (Tracer.Instance.StartActive("ValidateOrder"))
        {
            await ValidateOrderAsync(request);
        }

        using (var paymentScope = Tracer.Instance.StartActive("ProcessPayment"))
        {
            paymentScope.Span.SetTag("payment_method", request.PaymentMethod);
            await ProcessPaymentAsync(request);
        }

        using (Tracer.Instance.StartActive("FulfillOrder"))
        {
            return await FulfillOrderAsync(request);
        }
    }
    catch (Exception ex)
    {
        span.SetTag("error", true);
        span.SetTag("error.message", ex.Message);
        span.SetTag("error.type", ex.GetType().Name);
        throw;
    }
}
```

## Kubernetes Integration

### Datadog Agent Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: datadog-config
data:
  datadog.yaml: |
    api_key: <API_KEY>
    site: datadoghq.com

    # Logs
    logs_enabled: true
    logs_config:
      container_collect_all: true

    # APM
    apm_config:
      enabled: true
      env: prod

    # Process monitoring
    process_config:
      enabled: "true"

    # Kubernetes
    kubernetes_namespace_labels_as_tags:
      team: team
      environment: env
    kubernetes_pod_labels_as_tags:
      app: service
      version: version
```

### Autodiscovery

Configure container autodiscovery:

```yaml
# Pod annotations for autodiscovery
annotations:
  ad.datadoghq.com/order-api.check_names: '["openmetrics"]'
  ad.datadoghq.com/order-api.init_configs: '[{}]'
  ad.datadoghq.com/order-api.instances: |
    [{
      "prometheus_url": "http://%%host%%:9090/metrics",
      "namespace": "order_api",
      "metrics": ["*"]
    }]

  # Log configuration
  ad.datadoghq.com/order-api.logs: |
    [{
      "source": "dotnet",
      "service": "order-api",
      "log_processing_rules": [{
        "type": "multi_line",
        "name": "log_start_with_date",
        "pattern": "\\d{4}-\\d{2}-\\d{2}"
      }]
    }]
```

### Unified Service Tagging

Apply consistent tagging across all Kubernetes resources:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-api
  labels:
    tags.datadoghq.com/env: prod
    tags.datadoghq.com/service: order-api
    tags.datadoghq.com/version: "1.2.3"
spec:
  template:
    metadata:
      labels:
        tags.datadoghq.com/env: prod
        tags.datadoghq.com/service: order-api
        tags.datadoghq.com/version: "1.2.3"
    spec:
      containers:
        - name: order-api
          env:
            - name: DD_ENV
              valueFrom:
                fieldRef:
                  fieldPath: metadata.labels['tags.datadoghq.com/env']
            - name: DD_SERVICE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.labels['tags.datadoghq.com/service']
            - name: DD_VERSION
              valueFrom:
                fieldRef:
                  fieldPath: metadata.labels['tags.datadoghq.com/version']
```

## Database Integration

### SQL Server Integration

```yaml
init_config:

instances:
  - host: sqlserver.example.com
    port: 1433
    username: datadog
    password: <PASSWORD>
    database: master
    tags:
      - env:prod
      - service:order-api
    # Custom queries
    custom_queries:
      - query: |
          SELECT
            DB_NAME(database_id) as database_name,
            SUM(size * 8 / 1024) as size_mb
          FROM sys.master_files
          GROUP BY database_id
        columns:
          - name: database_name
            type: tag
          - name: database.size_mb
            type: gauge
```

### Redis Integration

```yaml
init_config:

instances:
  - host: redis.example.com
    port: 6379
    password: <PASSWORD>
    tags:
      - env:prod
      - service:order-api-cache
    keys:
      - pattern: "orders:*"
        type: "hash"
      - pattern: "sessions:*"
        type: "string"
```

---
[Back to Overview](./OVERVIEW.md)
