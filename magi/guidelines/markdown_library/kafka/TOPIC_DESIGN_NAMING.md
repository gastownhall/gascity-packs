# Topic Design and Naming

### Topic Semantics

A topic represents a category of messages with shared schema, retention, and access patterns. Topics are not queues — they are durable logs partitioned for parallelism. **One topic per event type or entity type is the standard pattern.** Multiplexing unrelated events into shared topics creates schema management nightmares and consumer complexity.

### Naming Conventions

Establish organization-wide naming patterns enforced through tooling:

| Element | Rule |
|:--------|:-----|
| Pattern | `{domain}.{entity}.{event-type}` or `{team}.{service}.{event}` |
| Examples | `orders.purchase.created`, `inventory.stock.adjusted`, `payments.transaction.completed` |
| Case | `lowercase.dot.separated` or `lowercase-hyphen-separated` — pick one and enforce it everywhere |
| Environment prefix | `dev.`, `staging.`, `prod.` only when sharing clusters across environments — prefer separate clusters |

Forbidden naming patterns:

- Generic names: `events`, `messages`, `data`, `queue`.
- Version suffixes for schema evolution: `orders-v2`, `orders-v3` — use Schema Registry instead.
- Timestamps or dates in topic names; topics are long-lived, not ephemeral.
- Underscores mixed with dots; Kafka metrics use dots as separators, causing collision.

### Topic Ownership

Every topic has a single owning team responsible for:

- Schema definition and evolution.
- Retention policy decisions.
- Access control configuration.
- Documentation and consumer onboarding.
- Monitoring and alerting.

Consumers do not own topics. Producers create topics through controlled processes, not ad-hoc client creation. **Disable `auto.create.topics.enable=false` in production clusters.**

### Topic Documentation

Maintain a registry documenting for each topic:

- Owning team and contact information.
- Message schema with field descriptions.
- Retention policy and rationale.
- Expected throughput and partition count justification.
- Authorized producers and consumers.
- Downstream dependencies.

---
[Back to Overview](./OVERVIEW.md)
