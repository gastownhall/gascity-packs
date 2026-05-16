# Monitoring and Observability — Required Telemetry

Every data store MUST be monitored on availability, latency percentiles (p50, p95, p99), throughput, error rates, capacity growth, and cost.

```csharp
public class DataStoreMonitoring
{
    private readonly ITelemetryClient _telemetry;

    public async Task<T> ExecuteWithMonitoringAsync<T>(
        string operationType,
        string storeName,
        Func<Task<T>> operation)
    {
        using var activity = Activity.StartActivity($"{storeName}.{operationType}");
        var stopwatch = Stopwatch.StartNew();
        try
        {
            var result = await operation();
            _telemetry.TrackMetric(new MetricTelemetry
            {
                Name = $"{storeName}.{operationType}.duration",
                Value = stopwatch.ElapsedMilliseconds,
                Properties =
                {
                    ["store"] = storeName,
                    ["operation"] = operationType,
                    ["success"] = "true"
                }
            });
            return result;
        }
        catch (Exception ex)
        {
            _telemetry.TrackException(ex, new Dictionary<string, string>
            {
                ["store"] = storeName,
                ["operation"] = operationType
            });
            _telemetry.TrackMetric(new MetricTelemetry
            {
                Name = $"{storeName}.{operationType}.error",
                Value = 1,
                Properties =
                {
                    ["store"] = storeName,
                    ["operation"] = operationType,
                    ["error_type"] = ex.GetType().Name
                }
            });
            throw;
        }
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
