# Schema Management

### Schema Registry Integration

Schema Registry provides:

- Central schema storage and versioning.
- Compatibility enforcement between versions.
- Schema ID encoding in messages for efficient serialization.

Configuration requirements:

- Register schemas before producing; reject unregistered schemas in production.
- Enable compatibility checking; reject incompatible evolutions.
- Cache schemas in producers and consumers to avoid per-message registry calls.

### Avro

```properties
key.serializer=io.confluent.kafka.serializers.KafkaAvroSerializer
value.serializer=io.confluent.kafka.serializers.KafkaAvroSerializer
key.deserializer=io.confluent.kafka.serializers.KafkaAvroDeserializer
value.deserializer=io.confluent.kafka.serializers.KafkaAvroDeserializer
```

**Evolution rules:**

| Compatibility | Allowed | Forbidden |
|:--------------|:--------|:----------|
| Backward | Add optional fields with defaults | Remove required fields |
| Forward | Remove optional fields | Add required fields without defaults |

### Protobuf

```properties
key.serializer=io.confluent.kafka.serializers.protobuf.KafkaProtobufSerializer
value.serializer=io.confluent.kafka.serializers.protobuf.KafkaProtobufSerializer
key.deserializer=io.confluent.kafka.serializers.protobuf.KafkaProtobufDeserializer
value.deserializer=io.confluent.kafka.serializers.protobuf.KafkaProtobufDeserializer
```

Better cross-language support; field deprecation support.

### Compatibility Modes

| Mode | Description | Use Case |
|:-----|:------------|:---------|
| **BACKWARD** (default) | New schema can read old data | Consumer-first deployments |
| FORWARD | Old schema can read new data | Producer-first deployments |
| FULL | Both backward and forward compatible | Independent deployments |
| NONE | No compatibility checking | Development only |

### Schema Evolution Rules (General)

For backward compatibility:

- Add optional fields with defaults.
- Do not remove required fields.
- Do not change field types.
- Do not rename fields.

For forward compatibility:

- Remove optional fields.
- Add required fields with defaults.
- Do not change field types.

Breaking changes require:

- New topic creation.
- Consumer migration coordination.
- Dual-publishing during transition.

### Subject Naming

| Strategy | Description |
|:---------|:------------|
| **TopicNameStrategy** (default) | One schema per topic: `{topic}-key`, `{topic}-value` |
| RecordNameStrategy | Schema per record type. Allows multiple event types per topic with independent evolution |
| TopicRecordNameStrategy | Combination — same record type can evolve independently per topic |

---
[Back to Overview](./OVERVIEW.md)
