# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Partition Key | High cardinality; in all query predicates; immutable |
| Document ID | String type; unique within partition; immutable |
| Container Names | Plural nouns: `orders`, `users`, `events` |
| Partition Key Property | `pk` or descriptive: `tenantId`, `userId` |
| Polymorphic Containers | `type` discriminator; include in queries |
| Timestamps | ISO 8601 strings or `_ts` for system time |
| Embedding | For bounded, co-accessed, infrequently updated data |
| Referencing | Store `id` and `pk`; include denormalized read-heavy properties |
| Queries | Single-partition; project specific fields; avoid `SELECT *` |
| Indexing | Include only queried paths; composite indexes for multi-property operations |
| Consistency | Session default; weaker for analytics; stronger for transactions |
| Client Lifecycle | Single `CosmosClient` per application |
| Bulk Operations | Enable `AllowBulkExecution`; use for high-volume writes |
| Transactions | Transactional batch within single partition |
| Change Feed | Idempotent handlers; separate lease container |
| TTL | Configure for temporary data; use for automatic cleanup |
| Security | Managed identity; private endpoints; least-privilege roles |
| Monitoring | Diagnostic logs; alerts on RU and 429 rates |
| Shakedown | Real account + canary docs + nine categories + classified outcome |
| Defense in Depth | Multi-region + explicit consistency + RU monitoring + partition validation + PITR + TTL + DR runbook + shakedown |

---

Following these rules produces Cosmos DB implementations that scale efficiently, operate predictably, and remain cost-effective. Partition key design and data modeling decisions made correctly at the start prevent expensive rearchitecture later. RU-conscious query development ensures production systems perform under load without surprise bills. Shakedown after every structural change ensures that the container behaves as declared in the live account, not just in unit tests against the emulator.

**Apply this guidance universally to all Azure Cosmos DB implementations across the organization.**

---
[Back to Overview](./OVERVIEW.md)
