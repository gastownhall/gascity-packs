# Kafka Connect

### Connector Types

| Type | Purpose | Examples |
|:-----|:--------|:---------|
| Source | Import from external systems into Kafka topics | JDBC, Debezium (CDC), S3, file systems |
| Sink | Export from Kafka topics to external systems | JDBC, Elasticsearch, S3, BigQuery |

### Distributed Connect Configuration

```properties
group.id={connect-cluster-id}
config.storage.topic=connect-configs            # RF=3, single partition
offset.storage.topic=connect-offsets            # RF=3, 25 partitions
status.storage.topic=connect-status             # RF=3, 5 partitions
```

### Connector Patterns

**JDBC source (incremental):**

```properties
connector.class=io.confluent.connect.jdbc.JdbcSourceConnector
mode=incrementing                               # or timestamp / timestamp+incrementing
poll.interval.ms=5000
batch.max.rows=1000
```

**Debezium CDC:**

```properties
connector.class=io.debezium.connector.mysql.MySqlConnector
snapshot.mode=initial
include.schema.changes=true
```

**S3 sink (Parquet, time-rotated):**

```properties
connector.class=io.confluent.connect.s3.S3SinkConnector
flush.size=1000
rotate.interval.ms=600000
format.class=io.confluent.connect.s3.format.parquet.ParquetFormat
```

### Connector-Level Settings

| Property | Value |
|:---------|:------|
| `tasks.max` | Maximum parallelism (actual tasks may be fewer based on source/sink constraints) |
| `errors.tolerance` | `all` for production with DLQ |
| `errors.deadletterqueue.topic.name` | `{topic}.dlq` |

### Single Message Transforms

| SMT | Purpose |
|:----|:--------|
| `InsertField` | Add fields from metadata |
| `ReplaceField` | Rename or drop fields |
| `MaskField` | Redact sensitive data |
| `TimestampRouter` | Route to time-partitioned topics |
| `RegexRouter` | Topic routing based on content |

Chain SMTs for complex transformations. Heavy transformations belong in stream processing, not Connect.

### Connector Monitoring

| Metric | Use |
|:-------|:----|
| `connector-status` | Running, paused, or failed |
| `task-status` | Running, failed, or unassigned per task |
| `source-record-poll-rate` | Records/sec for source connectors |
| `sink-record-send-rate` | Records/sec for sink connectors |

Configure alerting on connector failures. Implement automatic restart policies for transient failures.

---
[Back to Overview](./OVERVIEW.md)
