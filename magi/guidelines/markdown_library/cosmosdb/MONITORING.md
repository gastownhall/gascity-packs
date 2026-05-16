# Monitoring and Diagnostics

### Key Metrics

| Metric | Threshold |
|:-------|:----------|
| Total Requests | Volume and success/failure ratio |
| Request Charge (RU/s) | Consumed vs provisioned |
| 429 rate | > 1% indicates active throttling |
| Latency | p50, p99 server-side processing |
| Availability | Target 99.99% successful requests |
| Data Storage | Approaching quotas |
| Index Storage | Indexing overhead |
| Partition distribution | Hot partition detection |

### Azure Monitor Integration

Enable diagnostic logs to Log Analytics:

| Log type | Captures |
|:---------|:---------|
| `DataPlaneRequests` | Every operation with RU, latency, status |
| `QueryRuntimeStatistics` | Query execution details |
| `PartitionKeyStatistics` | Throughput and storage per partition |
| `ControlPlaneRequests` | Management operations |

### Alerting

Configure alerts for:
- RU consumption > 80% of provisioned (impending throttling)
- 429 error rate > 1% (active throttling)
- p99 latency > acceptable threshold
- Storage consumption > 80% of limit
- Replication lag > acceptable threshold (multi-region)

### SDK Diagnostics

```csharp
try
{
    var response = await container.ReadItemAsync<Order>(id, partitionKey);
}
catch (CosmosException ex)
{
    logger.LogError(ex, "Cosmos operation failed. Diagnostics: {Diagnostics}", ex.Diagnostics.ToString());
}
```

Diagnostics include retry attempts, endpoint contacted, timeline breakdown.

---
[Back to Overview](./OVERVIEW.md)
