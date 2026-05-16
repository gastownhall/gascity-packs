# Stream Processing — Kafka Streams vs ksqlDB

### Kafka Streams

Java library for stream processing.

**Pros:**

- Full programming flexibility.
- Complex stateful processing.
- Custom serialization.
- Unit-testable.

**Cons:**

- Requires Java development.
- More complex deployment.

**Use cases:** complex event processing, stateful transformations, custom business logic.

### ksqlDB

SQL interface for stream processing.

**Pros:**

- SQL familiarity.
- Quick prototyping.
- Built-in REST API.
- No coding required.

**Cons:**

- Limited to SQL operations.
- Less flexibility.
- Additional infrastructure.

**Use cases:** simple aggregations, stream joins, real-time dashboards.

---
[Back to Overview](./OVERVIEW.md)
