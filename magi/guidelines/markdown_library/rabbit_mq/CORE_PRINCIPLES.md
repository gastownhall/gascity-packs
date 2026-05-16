# Core Principles

These guidelines define strict, reliable, and scalable patterns for RabbitMQ message broker implementations, optimizing for:

- **Delivery Guarantees** — Message loss is unacceptable in production systems; every design decision accounts for acknowledgment semantics, persistence, and failure recovery.
- **Decoupled Architecture** — Publishers and consumers know nothing about each other; the broker is the contract boundary, not a pass-through pipe.
- **Backpressure Awareness** — Systems must handle message accumulation gracefully; uncontrolled queue growth is a failure mode, not a scaling opportunity.
- **Idempotent Processing** — Messages may arrive more than once; consumers must handle duplicates without corrupting state.
- **Observable by Default** — Every queue, exchange, and consumer produces metrics; invisible message flow is undebuggable message flow.

### Primary Rule: Acknowledge What You Complete

RabbitMQ's reliability model hinges on acknowledgments. A message is not processed until the consumer explicitly acknowledges it. Auto-acknowledgment trades safety for convenience — and loses. If the consumer crashes mid-processing with auto-ack enabled, the message vanishes. **Manual acknowledgment after successful processing is non-negotiable** for any workload where message loss matters. This single discipline separates toy implementations from production systems.

### Secondary Rule: Exchanges Route, Queues Buffer

Exchanges determine where messages go; queues hold messages until consumers retrieve them. Conflating these responsibilities — publishing directly to queues, using exchanges as storage — produces brittle topologies that resist change. Design exchanges for routing flexibility. Design queues for consumer workload patterns. The separation exists for a reason; honor it.

### AMQP Model Fundamentals

**Publishers** send messages to **exchanges**. Exchanges route messages to **queues** based on **bindings** and **routing keys**. **Consumers** subscribe to queues and process messages. This indirection enables:

- Multiple consumers sharing work from one queue (competing consumers)
- One message reaching multiple queues (fanout, topic routing)
- Routing logic changes without publisher modification
- Queue topology evolution independent of message producers

Understanding this model is prerequisite to everything that follows.

### Broker vs Application Responsibility

The broker handles routing, buffering, and delivery. It does **not** handle:

- Message transformation or enrichment
- Business logic validation
- Ordering guarantees beyond single-queue FIFO
- Exactly-once delivery (at-least-once with idempotent consumers is the pattern)

Applications own idempotency, schema validation, and processing semantics. The broker is infrastructure, not a business logic layer.

---
[Back to Overview](./OVERVIEW.md)
