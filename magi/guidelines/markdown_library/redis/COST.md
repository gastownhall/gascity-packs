# Cost Optimization

### Right-Sizing

- Start with smallest viable tier; scale up based on data.
- Monitor actual usage patterns.
- Scale based on data, not projections.
- Remove unused capacity if consistently underutilized.

### Reserved Capacity

| Commitment | Discount |
|:-----------|:---------|
| 1-year | Up to 35% |
| 3-year | Up to 55% |

Trade-off: less flexibility; best for stable workloads.

### Data Lifecycle Management

- Aggressive TTL reduces memory and tier requirements.
- Accept eviction rather than over-provisioning.
- Tiered caching — hot data in Redis, warm data in cheaper storage.
- Archive old data; don't pay to cache unused information.

### Tier Optimization

- Standard sufficient for most caching workloads.
- Premium only when clustering, VNet, or geo-replication is required.
- Don't pay for Premium features you don't use.
- Enterprise pricing: only when modules or active-active geo justify the cost.

### Multi-Tenant Cost Sharing

Shared instances reduce per-application fixed cost but require discipline around key namespacing. **Risk:** one application's behavior affects others.

---
[Back to Overview](./OVERVIEW.md)
