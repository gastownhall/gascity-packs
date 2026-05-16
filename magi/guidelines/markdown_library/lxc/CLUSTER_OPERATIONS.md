# Cluster Operations

### Cluster Architecture

Proxmox clusters provide:

- Centralized management of multiple nodes.
- Shared configuration via `pmxcfs`.
- Live migration between nodes.
- High availability with automatic failover.
- Unified authentication and permissions.

### Node Requirements

- Network connectivity for corosync (cluster communication).
- Time synchronization (NTP) within tight tolerance.
- Unique node names and IPs.
- Compatible Proxmox VE versions.

### Quorum Management

| Configuration | Quorum Source |
|:--------------|:--------------|
| 3+ nodes | Native quorum |
| 2-node cluster | External QDevice |

Quorum prevents split-brain scenarios. Majority of nodes must be operational for cluster to function. When quorum is lost:

- Cluster becomes read-only.
- No container operations possible.
- HA fencing triggered for affected nodes.

### Shared Storage Planning

For full cluster capabilities, implement shared storage:

- All nodes access same storage for live migration.
- Ceph provides integrated distributed storage.
- External NFS/iSCSI provides shared access.
- Local storage limits migration to offline mode.

### Cluster Expansion

```bash
# On new node:
pvecm add existing-node-ip
```

Ensure new node meets all cluster requirements before joining. Removing nodes requires careful procedure to maintain quorum.

---
[Back to Overview](./OVERVIEW.md)
