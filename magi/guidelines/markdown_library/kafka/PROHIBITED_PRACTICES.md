# Prohibited Practices

### Never Do

- Use `acks=0` or `acks=1` for data that matters — durability requires `acks=all`.
- Set `min.insync.replicas=1` in production — defeats replication purpose.
- Enable `unclean.leader.election.enable=true` without accepting data loss risk.
- Use `enable.auto.commit=true` with exactly-once processing requirements.
- Store secrets in message payloads without encryption.
- Create topics with replication factor 1 in production.
- Use generic topic names like `events` or `data`.
- Increase partition count as a quick fix without understanding ordering implications.
- Deploy consumers without monitoring lag.
- Use `latest` offset reset without understanding data-loss implications.
- Disable idempotence on producers handling critical data.
- Size consumer group larger than partition count.
- Run brokers on shared infrastructure with noisy neighbors.
- Ignore under-replicated partition alerts.
- Commit offsets before processing completes.
- Use synchronous sends in high-throughput producers.
- Store large blobs directly in Kafka instead of references to external storage.

---
[Back to Overview](./OVERVIEW.md)
