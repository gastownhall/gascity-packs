# Integration Patterns

### Request-Reply (RPC)

Synchronous request-response over async messaging:

1. Publisher creates exclusive reply queue.
2. Publisher sends request with `reply_to` and `correlation_id`.
3. Consumer processes request.
4. Consumer publishes response to `reply_to` with matching `correlation_id`.
5. Publisher correlates response and returns.

Use for synchronous operations that must traverse the message bus. Implement timeout handling for slow consumers and reply queue cleanup on disconnect.

### Publish-Subscribe

One-to-many event distribution:

1. Publisher sends to fanout or topic exchange.
2. Each subscriber has dedicated queue bound to exchange.
3. All subscribers receive independent copies.
4. Subscribers process independently.

Use for events with multiple interested consumers.

### Work Queue

Many-to-many task distribution:

1. Publishers send tasks to queue.
2. Multiple consumers compete for messages.
3. Each task processed by exactly one consumer.
4. Scale consumers based on queue depth.

Use for parallelizable work like image processing, report generation, or batch operations.

### Saga / Choreography

Distributed transactions through event chains:

1. Service A publishes event.
2. Service B consumes, processes, publishes next event.
3. Chain continues through services.
4. Compensation events handle failures.

No central coordinator — services coordinate via events. Use for multi-service workflows without distributed transaction coordinators.

### Event Sourcing Integration

RabbitMQ as event distribution layer:

1. Event store is source of truth.
2. Changes publish to RabbitMQ.
3. Consumers build read models, trigger side effects.
4. Replay from event store if consumers need rebuild.

**RabbitMQ is not an event store** — it is a distribution mechanism for events already persisted.

---
[Back to Overview](./OVERVIEW.md)
