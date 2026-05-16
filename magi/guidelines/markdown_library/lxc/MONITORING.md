# Monitoring and Observability

### Host-Level Metrics

| Metric | Indicator |
|:-------|:----------|
| CPU | Utilization, steal time, pressure |
| Memory | Usage, cache, swap, pressure |
| I/O | Throughput, latency, queue depth |
| Network | Bandwidth, packets, errors |

### Container-Level Metrics

| Metric | Indicator |
|:-------|:----------|
| CPU | Per-container usage against limits |
| Memory | RSS, cache, limit percentage |
| blkio | Read/write bytes and operations |
| Network | Per-interface statistics |

Access via API:

```bash
pvesh get /nodes/{node}/lxc/{vmid}/status/current
```

### Prometheus Integration

| Exporter | Scope |
|:---------|:------|
| `pve-exporter` | Cluster |
| `node-exporter` | Container (system metrics) |
| `cadvisor` | Docker (container metrics inside LXC) |

```yaml
# prometheus.yml excerpt
scrape_configs:
  - job_name: 'proxmox'
    static_configs:
      - targets: ['pve-node-01:9100', 'pve-node-02:9100']
  - job_name: 'containers'
    file_sd_configs:
      - files: ['/etc/prometheus/containers/*.yml']
        refresh_interval: 30s
```

Inside containers, deploy appropriate monitoring agents:

- Node Exporter for system metrics.
- Application-specific exporters.
- Log shipping agents (Filebeat, Fluentd, Promtail).

### Centralized Logging

| Component | Behavior |
|:----------|:---------|
| Application | stdout/stderr to journal |
| System | journald with forwarding |
| Aggregation | Loki, Elasticsearch, Splunk |

```bash
# Forward journal to remote syslog
echo "*.* @@syslog.example.com:514" >> /etc/rsyslog.d/50-remote.conf
systemctl restart rsyslog
```

```text
# Or use Fluent Bit for structured forwarding
[INPUT]
    Name systemd
    Tag container.*
[OUTPUT]
    Name loki
    Match container.*
    Host loki.example.com
```

Container logs handled at multiple levels:

- **Application logs** — ship to centralized logging (ELK, Loki).
- **System logs** — journald inside container; forward critical entries.
- **Proxmox task logs** — `/var/log/pve/tasks/` for operation history.

### Alerting Thresholds

Configure alerts for:

- CPU sustained above 80% for 10 minutes.
- Memory usage above 90% of limit.
- Disk space below 20% free.
- Network errors exceeding threshold.
- Container restart events.
- Backup failures.

---
[Back to Overview](./OVERVIEW.md)
