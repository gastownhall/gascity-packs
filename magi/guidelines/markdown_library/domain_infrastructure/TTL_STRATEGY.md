# TTL Strategy

### TTL Fundamentals

Time-to-Live controls how long resolvers and clients cache a DNS response before re-querying the authoritative server. Longer TTLs reduce DNS query volume and improve resolution speed for returning visitors. Shorter TTLs enable faster propagation of record changes.

### TTL by Record Type

TTL values must match the operational characteristics of each record type. Do not apply a uniform TTL across all records.

| Record Class | Recommended TTL | Rationale |
|:-------------|:----------------|:----------|
| Stable records (MX, SPF/DKIM/DMARC TXT, NS) | 3600–86400s (1–24h) | Change infrequently; long TTLs reduce query load |
| Standard production (A, AAAA, CNAME) | 300–3600s (5min–1h) | Balances cache efficiency with reasonable change propagation |
| Records pre-change (migration, cutover) | 60–300s | Lower at least 48h before the change; raise back after verification |
| Failover / DR records | ≤ 60s | Accept higher query volume as the cost of rapid failover |

### TTL Anti-Patterns

Setting all records to 60-second TTL generates unnecessary query volume, increases resolution latency, and provides no benefit for records that change once a year. Conversely, setting production A records to 86400-second TTL makes emergency migrations take 24 hours to fully propagate — an eternity during an incident.

Forbidden:

- TTL of 0 on production records — overloads authoritative servers, increases resolution latency, no operational benefit over 60 seconds.
- Blanket 60-second TTL on all records regardless of change frequency.
- 86400-second TTL on production A records without a pre-change TTL reduction plan.

---
[Back to Overview](./OVERVIEW.md)
