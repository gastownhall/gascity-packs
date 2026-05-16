# Migration and High Availability

### Offline Migration

```bash
pct migrate 101 target-node
```

Requirements:

- Container must be stopped.
- Target node must have access to container storage (shared storage or replication).
- Network configuration compatible with target node.

### Live Migration

```bash
pct migrate 101 target-node --online
```

Requirements:

- Shared storage accessible from both nodes.
- Network bridges with same names on both nodes.
- Sufficient resources on target node.
- Container must not have local-only resources (certain bind mounts).

Process:

1. Memory state iteratively copied to target.
2. Container briefly paused for final state sync.
3. Container resumed on target node.
4. Source container removed.

### Bulk Migration

```bash
#!/bin/bash
# Migrate all containers from node for maintenance
SOURCE_NODE="pve-node-01"
TARGET_NODE="pve-node-02"
for vmid in $(pvesh get /nodes/$SOURCE_NODE/lxc --output-format json | jq -r '.[].vmid'); do
    echo "Migrating container $vmid..."
    pct migrate $vmid $TARGET_NODE --online
    sleep 10  # Avoid overwhelming target
done
```

### High Availability Configuration

```bash
ha-manager add ct:101 --group production --state started
```

| Requirement | Criticality |
|:------------|:------------|
| Minimum 3 nodes for quorum | Mandatory |
| Shared storage accessible from all HA-eligible nodes | Mandatory |
| Fencing configuration | Mandatory |
| Time synchronization | Mandatory |
| Redundant cluster network | Recommended |

### Quorum and Fencing

| Quorum | Nodes |
|:-------|:------|
| Native (Corosync) | 3+ |
| QDevice (external) | 2 |

| Fencing Method | Reliability |
|:---------------|:------------|
| IPMI | High — hardware-based power fencing |
| iLO / DRAC | High — vendor management interfaces |
| Watchdog | Medium — software watchdog timer |

```bash
# Configure IPMI fencing
pvecm set --fencing 'ipmi:10.0.0.11,10.0.0.12,10.0.0.13'
# Add container to HA
ha-manager add ct:101 --group production --state started
# Configure HA group
ha-manager groupadd production --nodes pve-node-01,pve-node-02 --nofailback 0
```

**Without proper fencing, HA is unsafe and should not be enabled.**

### Migration Planning

For planned maintenance:

1. Disable HA on affected containers temporarily.
2. Migrate containers to other nodes.
3. Perform maintenance.
4. Migrate containers back (if preferred).
5. Re-enable HA.

For capacity planning, ensure the cluster can sustain N-1 node failure with acceptable performance degradation.

---
[Back to Overview](./OVERVIEW.md)
