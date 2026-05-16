# Cost Optimization

### Request Quotas

| Service | Limit | Period |
|:--------|:------|:-------|
| App Configuration Standard | 20,000 requests | per hour |
| Key Vault | 4,000 transactions | per 10 seconds per vault |

### App Configuration Cost Drivers

| Factor | Impact | Optimizations |
|:-------|:-------|:--------------|
| Storage | Negligible | — |
| Requests | Significant | Cache aggressively; refresh ≥ 5 min; sentinel-key pattern |

### Key Vault Cost Drivers

| Factor | Impact | Optimizations |
|:-------|:-------|:--------------|
| Secret operations | Moderate | Cache values in memory; avoid unnecessary list operations |
| HSM operations | High | Use Standard vault unless HSM compliance required |

Design applications to:
- Cache configuration and secrets appropriately
- Avoid per-request configuration lookups
- Batch operations where supported
- Monitor request counts and alert before quota exhaustion

---
[Back to Overview](./OVERVIEW.md)
