# Exchange Types and Routing

### Direct Exchanges

Route messages to queues where binding key exactly matches routing key:

- Use for point-to-point messaging with known destinations.
- One routing key maps to one or more queues with identical bindings.
- The default exchange (empty-string name) routes directly to queue names.

Direct exchanges suit command patterns where the destination is explicit and stable.

### Topic Exchanges

Route messages based on pattern matching with wildcards:

- `*` matches exactly one word: `order.*.created` matches `order.us.created`.
- `#` matches zero or more words: `order.#` matches `order.us.west.created`.
- Enable flexible routing without exchange proliferation.

Topic exchanges suit event patterns where consumers select relevant event subsets. A single `events.topic` exchange serves dozens of consumer patterns through binding key variation.

### Fanout Exchanges

Route messages to all bound queues regardless of routing key:

- Broadcasting to multiple consumers
- Cache invalidation across services
- Audit logging that captures everything

Fanout ignores routing keys entirely. Every bound queue receives every message. Use when all subscribers want all messages.

### Headers Exchanges

Route based on message header attributes rather than routing key:

- Complex routing logic beyond string patterns
- Multi-attribute routing decisions
- `x-match: all` requires all headers match; `x-match: any` requires at least one

Headers exchanges add flexibility at the cost of complexity. **Prefer topic exchanges unless header-based routing is genuinely required.**

### Exchange Selection Criteria

| Pattern | Exchange Type | Rationale |
|:--------|:--------------|:----------|
| Command to specific service | Direct | Known destination, exact routing |
| Event to interested parties | Topic | Flexible subscription patterns |
| Broadcast to all | Fanout | No routing logic needed |
| Complex multi-attribute routing | Headers | Beyond string pattern capability |

Default to topic exchanges for event-driven architectures. They provide flexibility without premature optimization toward direct or fanout.

### Exchange-to-Exchange Bindings

Exchanges can bind to other exchanges, creating routing hierarchies:

- Aggregate events from multiple sources
- Apply secondary routing logic
- Implement complex routing DAGs

Use sparingly. Deep exchange chains complicate debugging and increase routing latency.

---
[Back to Overview](./OVERVIEW.md)
