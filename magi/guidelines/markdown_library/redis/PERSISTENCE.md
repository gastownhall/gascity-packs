# Persistence Configuration

### Persistence Options

Azure Cache for Redis Premium tier offers persistence:

| Option | Behavior |
|:-------|:---------|
| **RDB** (point-in-time snapshots) | Periodic snapshots to Azure Storage; configurable frequency (15 min, 1h, 6h, 12h, 24h); fork-based; data loss = changes since last snapshot |
| AOF | **Not supported in Azure Cache for Redis** — use Enterprise tier with persistence configuration or self-managed Redis for AOF-like durability |

### When to Enable Persistence

| Enable when | Skip when |
|:------------|:----------|
| Cache warm-up time is unacceptable (large dataset, slow source) | Application handles cache misses efficiently |
| Restart should preserve cache state | Data easily reconstructed from source |
| Disaster recovery requires cache state recovery | Cost of persistence storage not justified |

### RDB Trade-offs

| Benefits | Costs |
|:---------|:------|
| Faster restart (load snapshot vs empty cache) | Storage costs for snapshots |
| Reduced database load during warm-up | Brief latency spike during snapshot (fork) |
| Point-in-time recovery capability | Data loss window between snapshots |

---
[Back to Overview](./OVERVIEW.md)
