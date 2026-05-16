# Multi-Tenant and Shared Instance Patterns

### Database Isolation

Redis supports 16 databases (0–15) by default:

- Usage: `SELECT 1` switches to database 1.
- Keys in different databases don't conflict.
- **Limitations:** no individual database sizing or eviction; admin commands affect all databases.
- **Not recommended for security isolation.**

### Key Prefix Isolation

Namespace keys by application or tenant:

```text
{app}:{entity}:{id}      — webapp:cache:user:123
{tenant}:{entity}:{id}   — tenant-abc:session:xyz
{service}:{entity}:{id}  — service-a:ratelimit:api
```

Application configuration specifies prefix; all operations use it. Use `SCAN` with pattern to count keys per namespace.

### Resource Governance in Shared Instances

| Concern | Approach |
|:--------|:---------|
| Memory | Monitor per-prefix key counts; alert on prefix growth exceeding allocation; implement application-level quotas |
| Connections | Pool sizing per application; monitor connections by client name (set in connection string); alert when single application exceeds threshold |
| Throughput | No native per-tenant throttling; implement application-level rate limiting; use separate cache if one tenant dominates |

### When to Separate Caches

| Separate when | Share when |
|:--------------|:-----------|
| Security requirements mandate isolation | Applications trust each other |
| One application's SLA differs significantly | Resource usage is predictable and balanced |
| Resource consumption is highly imbalanced | Cost optimization is priority |
| Different eviction policies required | Operational simplicity valued |
| Compliance requires dedicated infrastructure | — |

---
[Back to Overview](./OVERVIEW.md)
