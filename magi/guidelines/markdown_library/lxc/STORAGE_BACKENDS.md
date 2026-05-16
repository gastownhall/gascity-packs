# Storage Backend Selection

### Available Storage Types

| Backend | Type | Performance | Shared | Snapshots | Live Migration | Use Case |
|:--------|:-----|:------------|:-------|:----------|:---------------|:---------|
| `local` | Local | Variable | No | No | No | Directory-based local filesystem |
| `local-lvm` | Local | High | No | Yes (thin) | No | Single-node high performance |
| `local-zfs` | Local | High | No | Yes (native) | No | Single-node with advanced features |
| `nfs` | Shared | Medium | Yes | Depends | Yes | General shared storage |
| `cifs` | Shared | Medium | Yes | No | Yes | SMB/CIFS shares |
| `ceph/rbd` | Shared | High | Yes | Yes | Yes | Production clusters |
| `cephfs` | Shared | Medium | Yes | Yes | Yes | Shared filesystem needs |
| `iscsi` | Shared | Variable | Yes | No | Yes | iSCSI targets |

### LVM Thin

```bash
# Create thin pool
lvcreate -L 100G -T pve/data
# Monitor usage
lvs -a -o +devices,metadata_percent,data_percent
```

- Enables efficient snapshots and space-efficient allocation.
- Monitor thin pool usage; expansion required before exhaustion.
- Configure monitoring alerts at **80% thin pool utilization**.

### ZFS

Features: native snapshots, compression, checksumming, encryption, deduplication.

| Tunable | Recommendation |
|:--------|:---------------|
| `recordsize` | Match workload block size |
| `arc_max` | Account for ARC memory consumption in host memory planning |
| `compression` | `lz4` for balance |

### Ceph RBD

Requirements:

- Minimum 3 nodes for production reliability.
- Dedicated cluster network for OSD replication.
- SSD-backed pools for metadata-heavy workloads.
- Network separation for cluster traffic vs client traffic.

Monitor placement groups and recovery status.

### NFS

Considerations:

- Network latency impacts performance.
- Single point of failure without HA NFS.

### Root Filesystem Sizing

| Workload | Size |
|:---------|:-----|
| Minimal services (DNS, DHCP) | 4–8 GB |
| Application servers | 16–32 GB |
| Database servers | Size for data growth + 20% headroom |
| Development environments | 32–64 GB for tooling and dependencies |

**Do not create containers with default sizes and "fix it later"** — storage expansion is more complex than correct initial sizing.

---
[Back to Overview](./OVERVIEW.md)
