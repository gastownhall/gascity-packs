# Resource Allocation

### Memory Management

Hard limits prevent OOM conditions affecting other containers:

- `memory` — maximum RAM in megabytes; container processes killed when exceeded.
- `swap` — swap space allocation; **set to 0 for predictable performance**.

**Sizing methodology:**

1. Baseline — monitor idle memory consumption after initial setup.
2. Load testing — measure peak consumption under realistic workload.
3. Headroom — add 20–30% above peak for burst capacity.
4. Review — adjust quarterly based on actual utilization metrics.

**Memory overcommit considerations:**

- Production environments should not overcommit beyond 120% of physical RAM.
- Monitor for memory pressure indicators (`/proc/meminfo`, `oom_kill` counts).
- Containers with critical workloads should have guaranteed memory via cgroup reservations.

### CPU Allocation

| Parameter | Purpose |
|:----------|:--------|
| `cores` | Maximum CPU cores. Does not guarantee availability — other containers compete |
| `cpulimit` | Fractional CPU limit (e.g., 1.5 = 150% of one core), regardless of `cores` setting |
| `cpuunits` | Relative scheduling weight (default 1024). Higher = proportionally more CPU during contention |

**Allocation patterns:**

| Workload | Cores | CPU Units | Notes |
|:---------|:------|:----------|:------|
| Database servers | Fixed allocation matching workload parallelism | High (e.g., 2048) | Consistent priority |
| Web servers | Moderate cores with cpulimit | Default | Prevent runaway requests from saturating host |
| Background workers | Burstable | Lower (e.g., 512) | Low priority, burst capable |
| Development containers | Low base | Default | Burst capability |

### Control Groups (cgroups)

| Version | Status | Notes |
|:--------|:-------|:------|
| cgroups-v1 | Legacy | Hierarchical, per-controller |
| **cgroups-v2** | Current | Unified hierarchy, better pressure stall information |

cgroup v2 configuration in container config:

```ini
lxc.cgroup2.memory.max = 2G
lxc.cgroup2.memory.swap.max = 0
lxc.cgroup2.cpu.max = 200000 100000
lxc.cgroup2.io.max = 8:0 rbps=104857600 wbps=52428800
```

### I/O Constraints

```ini
mp0: local-lvm:8,mp=/data,backup=1,mbps_rd=100,mbps_wr=50
```

| Parameter | Purpose |
|:----------|:--------|
| `mbps_rd` | Read bandwidth limit in MB/s |
| `mbps_wr` | Write bandwidth limit in MB/s |
| `iops_rd` | Read IOPS limit |
| `iops_wr` | Write IOPS limit |

Apply I/O limits to prevent storage-bound containers from impacting others, particularly on shared storage backends.

### Resource Monitoring

- Proxmox web interface provides per-container CPU, memory, network, and disk metrics.
- `pct exec <vmid> -- top` for real-time process visibility.
- Export metrics to external monitoring (Prometheus, InfluxDB) for historical analysis.
- Alert on sustained high utilization indicating under-provisioning.
- Alert on consistently low utilization indicating over-provisioning and waste.

---
[Back to Overview](./OVERVIEW.md)
