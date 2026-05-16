# Multi-Region Configuration

### Distribution Topologies

| Topology | Description |
|:---------|:------------|
| Single region | Simplest configuration; no replication overhead |
| Multi-region single write | One write region, multiple read replicas; automatic failover |
| Multi-region multi-write | Any region accepts writes; conflict resolution required |

### Read Region Selection

```csharp
var options = new CosmosClientOptions
{
    ApplicationRegion = Regions.WestUS2
};
```

Or specify region priority:
```csharp
var options = new CosmosClientOptions
{
    ApplicationPreferredRegions = new List<string> { Regions.WestUS2, Regions.EastUS, Regions.WestEurope }
};
```

### Write Region Failover

With single-write multi-region:
- Automatic failover when write region becomes unavailable
- Configure failover priority in Azure Portal
- Application automatically redirects using SDK

### Multi-Write Conflict Resolution

When multi-write is enabled, conflicts are possible:
- **Last Write Wins (LWW)**: Document with highest `_ts` wins; default and sufficient for most cases
- **Custom**: Stored procedure resolves conflicts; use for business-specific merge logic

### Consistency and Multi-Region

- Strong consistency: available only with single write region; reads wait for replication
- Session consistency: session tokens must be propagated for cross-region read-your-writes
- Eventual / Consistent Prefix: best suited for multi-write; accept convergence delay

---
[Back to Overview](./OVERVIEW.md)
