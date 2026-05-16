# Message Design and Serialization

### Message Structure

Every message consists of:

- **Key** — determines partition routing; may be null for round-robin.
- **Value** — the payload, the actual event or data.
- **Headers** — metadata not part of the payload (trace IDs, source identifiers, content type).
- **Timestamp** — producer-set or broker-set; used for time-based operations.

### Serialization Formats

| Format | Use For | Notes |
|:-------|:--------|:------|
| **Avro** (recommended) | Most cases | Schema-enforced, compact binary, Schema Registry integration, strong typing with generated classes |
| **Protobuf** | Cross-language schemas | More compact for nested structures, excellent evolution, requires explicit schema management |
| **JSON** | Development / rapid iteration | Human-readable, no schema enforcement without external validation, larger payloads |
| Plain bytes/strings | Legacy integration only | No schema evolution; consumer must know how to interpret |

### Message Size Guidelines

- **Target**: under 100 KB per message for optimal performance.
- **Warning threshold**: 500 KB — consider chunking or external storage.
- **Hard limit**: default broker `message.max.bytes` is 1 MB. Increasing affects memory pressure.
- **Large payloads**: store in object storage; publish a reference in Kafka.

### Header Usage

Use headers for cross-cutting concerns:

- Correlation IDs for distributed tracing.
- Source system identification.
- Content type when format varies.
- Compression indicator for payload-level compression.
- Encryption metadata.

**Do not use headers for business data.** Headers are not schema-enforced and easily dropped or corrupted by intermediate processors.

---
[Back to Overview](./OVERVIEW.md)
