# Architecture and Topology Design

### Virtual Host Isolation

Virtual hosts (vhosts) provide logical separation within a single RabbitMQ instance:

- **Environment isolation:** `/production`, `/staging`, `/development`
- **Tenant isolation:** `/tenant-acme`, `/tenant-globex`
- **Application isolation:** `/orders`, `/notifications`, `/analytics`

Each vhost has independent exchanges, queues, bindings, users, and permissions. Cross-vhost communication requires explicit federation or shovel configuration — it is not automatic, and that is intentional.

### Naming Conventions

Consistent naming enables automation, monitoring, and troubleshooting:

| Element | Format | Examples |
|:--------|:-------|:---------|
| Exchange | `{domain}.{purpose}.{type}` | `orders.created.topic`, `notifications.fanout.direct` |
| Queue | `{service}.{action}.{qualifier}` | `billing.invoice-generate.retry`, `shipping.label-create.dlq` |
| Routing key | Dot-delimited hierarchy | `order.created.us-west`, `user.updated.premium` |

Avoid generic names like `queue1` or `main-exchange`. Names must convey purpose without requiring documentation lookup.

### Topology Ownership

| Role | Owns |
|:-----|:-----|
| Infrastructure team | Cluster configuration, vhost creation, user management, monitoring |
| Application team | Exchange and queue declarations, binding configuration, consumer implementation |
| Shared | Capacity planning, performance tuning, incident response |

Queues and exchanges are declared by the application that uses them, typically at startup. Infrastructure provides the cluster; applications provide the topology.

### Declaration Patterns

Applications declare their required topology on startup:

1. Declare exchanges before publishing.
2. Declare queues before consuming.
3. Declare bindings to connect exchanges and queues.
4. Use `passive` declarations to verify existence without creation when appropriate.

Declarations are idempotent — redeclaring an identical exchange or queue succeeds. Redeclaring with different parameters fails. This prevents accidental topology corruption but requires consistency across all declaring applications.

### Topology Versioning

When topology must change:

1. Add new exchanges/queues alongside existing ones.
2. Migrate publishers to the new exchange.
3. Drain old queues.
4. Remove deprecated topology.

**Never modify existing exchange or queue parameters in production.** The broker rejects parameter mismatches, causing application startup failures.

---
[Back to Overview](./OVERVIEW.md)
