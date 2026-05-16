# Throughput Management

### Throughput Models

| Model | Billing | Best For |
|:------|:--------|:---------|
| **Provisioned** | Hourly regardless of usage | Predictable steady workloads; cost optimization; sustained > 10,000 RU/s |
| **Autoscale** | Highest RU/s consumed each hour (50% premium at steady high utilization) | Variable workloads with peaks/valleys; minimum max 1,000 RU/s |
| **Serverless** | Per RU consumed | Dev/test; low-traffic with unpredictable bursts; max 5,000 RU/s burst, single region |

### Throughput Selection

**Use provisioned** when:
- Workload is predictable and steady
- Cost optimization is priority over convenience
- High throughput sustained (>10,000 RU/s)

**Use autoscale** when:
- Workload has predictable peaks and valleys
- Traffic patterns change throughout the day
- Acceptable to pay premium for automatic scaling

**Use serverless** when:
- Development or test environments
- Low-traffic applications with unpredictable bursts
- New applications before usage patterns are understood

### RU Budgeting

| Operation | Approximate RU |
|:----------|:---------------|
| Point read (1KB document) | 1 RU |
| Point read (10KB document) | ~3 RU |
| Create (1KB document) | 5-10 RU |
| Replace (1KB document) | 5-10 RU |
| Delete | 5-10 RU |
| Query (1KB doc, indexed filter) | 2-3 RU |
| Query (cross-partition) | RU × partition count |

### Rate Limiting (HTTP 429)

When requests exceed provisioned throughput:
- Cosmos DB returns HTTP 429 (`TooManyRequests`)
- Response includes `x-ms-retry-after-ms` header
- SDKs implement automatic retry with exponential backoff
- Configure maximum retry attempts and wait time

Application design must handle 429s gracefully:
- Implement circuit breakers for sustained rate limiting
- Queue and retry for batch operations
- **Alert on elevated 429 rates** — indicates under-provisioned throughput

---
[Back to Overview](./OVERVIEW.md)
