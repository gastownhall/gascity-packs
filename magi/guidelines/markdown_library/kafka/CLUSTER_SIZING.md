# Cluster Sizing and Capacity

### Broker Count

Minimum 3 brokers for production (supports RF=3 with one-failure tolerance). Add brokers for:

- Increased throughput requirements.
- Partition leadership distribution.
- Disk capacity across more nodes.
- Rack/AZ distribution for availability.

### Storage Planning

```text
storage_gb = (daily_ingest_gb × retention_days × replication_factor) / broker_count
```

Add **30% headroom** for compaction overhead, partition reassignment during maintenance, and growth buffer.

Use dedicated disks for Kafka log directories. SSDs improve latency; HDDs are acceptable for throughput-oriented workloads. **Never share disks with other applications or OS.**

### Memory Planning

Per broker:

- JVM heap: 6–8 GB typical.
- Page cache: remaining RAM (Kafka relies heavily on OS page cache).
- Total: 32–64 GB RAM per broker for production workloads.

More memory means more data cached, reducing disk reads. Size page cache to hold active segment data.

### Network Planning

```text
inbound_bandwidth  = producer_throughput_mb/s
outbound_bandwidth = producer_throughput_mb/s × (replication_factor - 1 + consumer_count)
```

Provision **10 Gbps minimum** for production. Inter-broker replication dominates network usage; size accordingly.

---
[Back to Overview](./OVERVIEW.md)
