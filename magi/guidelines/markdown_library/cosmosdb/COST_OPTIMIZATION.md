# Cost Optimization

### RU Reduction Strategies

- Right-size documents — smaller documents cost fewer RUs
- Optimize queries — avoid cross-partition; use efficient filters
- Tune indexing — exclude unqueried paths
- Use point reads — more efficient than queries when ID and partition key are known
- Increase consistency level — eventually consistent reads cost 50% less than strong

### Throughput Optimization

- Use autoscale for variable workloads; avoid paying for peak provisioning 24/7
- Use serverless for development and low-traffic environments
- Consolidate containers with shared throughput for small workloads
- Schedule throughput scaling for predictable peaks (batch processing windows)

### Storage Optimization

- Implement TTL for temporary data
- Archive cold data to cheaper storage (Blob)
- Compress large text/JSON fields before storage
- Exclude large unqueried fields from indexing

### Reserved Capacity

For predictable, long-term workloads:

| Term | Discount |
|:-----|:---------|
| 1-year reservation | ~20% |
| 3-year reservation | ~35% |

Commitment to specific RU/s quantity. Apply to normalized RU/s across regions and consistency levels.

### Throughput Model Decision Tree

```text
sporadic-traffic           → serverless
development-environment    → serverless
peak < 5,000 RU/s          → consider serverless
predictable-load           → provisioned
variable-predictable       → autoscale
sustained-high-throughput  → provisioned
multi-region-required      → cannot use serverless
```

---
[Back to Overview](./OVERVIEW.md)
