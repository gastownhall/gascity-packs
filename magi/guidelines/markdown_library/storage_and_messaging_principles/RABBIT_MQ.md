# RabbitMQ

### What It Is

RabbitMQ is an open-source message broker implementing AMQP (Advanced Message Queuing Protocol). It provides reliable messaging with flexible routing, multiple exchange types, and rich feature set for complex messaging scenarios.

### Core Strengths

- **Flexible Routing**: Direct, fanout, topic, and header exchanges for complex routing
- **Reliability**: Persistent messages, acknowledgments, publisher confirms
- **Feature Rich**: Dead-letter queues, message TTL, priority queues, delayed messages
- **Protocol Support**: AMQP 0.9.1, MQTT, STOMP
- **Clustering**: High availability with mirrored queues
- **Management UI**: Built-in web UI for monitoring and administration
- **Open Source**: No vendor lock-in; self-host or use managed service

### Core Weaknesses

- **Operational Complexity**: Cluster management, split-brain handling, capacity planning
- **Message Size**: Large messages impact performance (store externally)
- **Scaling Write Throughput**: Single queue has throughput limits; requires sharding
- **Memory Usage**: Queue depth impacts memory; backpressure when exhausted
- **No Native Cloud Integration**: Requires self-hosting or third-party managed service in Azure

### Ideal Use Cases

- Complex routing requirements (topic-based, content-based)
- When you need dead-letter queues, message TTL, priorities
- Integration with non-Azure systems
- Multi-cloud or hybrid deployments
- High throughput with sophisticated delivery semantics
- When avoiding cloud vendor lock-in is a priority

### Avoid When

- Simple point-to-point queuing suffices (use Storage Queues)
- Team lacks messaging expertise (operational complexity)
- Azure-native solution preferred (use Service Bus)
- Extremely high throughput needed (consider Kafka)
- Log-based event streaming is the primary pattern

### Exchange Types

| Type        | Routing                            | Use Case                              |
|-------------|------------------------------------|---------------------------------------|
| **Direct**  | Exact routing key match            | Task queues, specific routing         |
| **Fanout**  | All bound queues                   | Broadcast, pub/sub                    |
| **Topic**   | Pattern matching (*.logs, #.error) | Log aggregation, hierarchical routing |
| **Headers** | Message header matching            | Content-based routing                 |

### Message Flow

```
Producer → Exchange → Binding → Queue → Consumer
                ↓
           Routing Key determines which queue(s)
```

### Reliability Patterns

**Publisher Confirms**:
```
1. Publisher enables confirm mode on channel
2. Publisher sends message
3. Broker acknowledges receipt
4. If no ack, publisher retries
```

**Consumer Acknowledgments**:
```
1. Consumer receives message
2. Consumer processes message
3. Consumer sends ack (success) or nack (failure)
4. If nack or timeout: message requeued or dead-lettered
```

**Persistence**:
- Durable queues: Queue survives broker restart
- Persistent messages: Messages written to disk
- Both required for full durability

### Dead Letter Exchange

```
Main Queue --[reject/expire/max-length]--> Dead Letter Exchange --> Dead Letter Queue
```

Configure dead-letter exchange for:
- Failed message inspection
- Poison message handling
- Message expiration tracking
- Retry patterns with backoff

### High Availability

**Mirrored Queues (Classic)**:
- Queue replicated to multiple nodes
- Leader handles all operations; mirrors sync
- Automatic failover on leader failure

**Quorum Queues (Recommended)**:
- Raft-based consensus for durability
- Better data safety guarantees
- Use for all durable, replicated queues

### Capacity Planning

Monitor:
- Queue depth: Messages awaiting consumption
- Message rates: Publish rate vs consume rate
- Memory usage: Impacts when approaching limit
- Disk usage: For persistent messages
- Connection/channel count: Per-client resources

Scale horizontally by:
- Sharding queues across cluster nodes
- Multiple consumer instances per queue
- Consistent hash exchange for workload distribution

---
[Back to Overview](./OVERVIEW.md)
