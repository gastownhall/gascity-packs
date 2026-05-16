# Message Design and Serialization

### Message Properties

Essential properties for every message:

| Property | Required | Description |
|:---------|:--------:|:------------|
| `content_type` | yes | MIME type (`application/json`, `application/protobuf`) |
| `content_encoding` | no | Compression if applied (`gzip`, `deflate`) |
| `delivery_mode` | yes | `1` (non-persistent) or `2` (persistent) |
| `message_id` | yes | Unique identifier for deduplication and tracing |
| `correlation_id` | conditional | Links related messages (request/response) |
| `timestamp` | yes | Publication time (Unix epoch milliseconds) |
| `type` | recommended | Message type discriminator for polymorphic handlers |
| `app_id` | recommended | Publishing application identifier |

### Payload Design

Messages must be self-describing and versioned:

- Include schema version in payload or headers.
- Design for forward compatibility (ignore unknown fields).
- Design for backward compatibility (defaults for missing fields).
- Keep payloads focused; one message type per logical event.

### Serialization Formats

| Format | Size | Schema | Speed | Use Case |
|:-------|:----:|:------:|:-----:|:---------|
| JSON | Large | Implicit | Slow | Debugging, interop, low volume |
| Protocol Buffers | Small | Explicit | Fast | High volume, cross-language |
| MessagePack | Small | Implicit | Fast | JSON-like with size benefits |
| Avro | Small | Explicit | Fast | Schema registry integration |

Production systems processing significant volume use binary formats. JSON is acceptable for low-volume or debugging scenarios.

### Message Size Guidelines

- Target messages under **128KB** for optimal throughput.
- Messages over **1MB** degrade broker performance.
- For large payloads, store data externally and pass references.
- Compress large text payloads if transmission is the bottleneck.

### Idempotency Keys

Include identifiers enabling duplicate detection:

- `message_id` as unique identifier.
- Business-level idempotency key in payload.
- Combination of entity ID + operation + timestamp.

Consumers track processed idempotency keys to reject duplicates. The broker provides at-least-once delivery; idempotency provides effectively-once processing.

---
[Back to Overview](./OVERVIEW.md)
