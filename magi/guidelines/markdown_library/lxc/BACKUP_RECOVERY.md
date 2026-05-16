# Backup and Disaster Recovery

### Backup Modes

| Mode | Downtime | Consistency | Use |
|:-----|:---------|:------------|:----|
| **Snapshot** | None | Application-dependent | Default for most workloads |
| Suspend | Brief | High | Applications not handling snapshots gracefully |
| Stop | Full | Maximum | Critical data requiring guaranteed consistency |

### Backup Configuration

```bash
vzdump 101 \
    --compress zstd \
    --mode snapshot \
    --storage backup-store \
    --mailnotification always \
    --mailto admin@example.com
```

Scheduled backups via `/etc/pve/jobs.cfg` or Datacenter → Backup in GUI.

### Proxmox Backup Server Integration

Features: incremental backups, deduplication, encryption, verification.

```bash
# Configure PBS datastore
pvesm add pbs backup-store --server backup.example.com --datastore containers
# Schedule backup job
cat >> /etc/pve/jobs.cfg << 'EOF'
vzdump: backup-job-01
    schedule daily 02:00
    storage backup-store
    mode snapshot
    compress zstd
    maxfiles 7
    node pve-node-01
    vmid 101,102,103
EOF
```

### Backup Storage

- Local backups for rapid recovery; limited by local storage capacity.
- Remote backups (PBS, NFS, S3) for disaster recovery; accepts transfer latency.
- Maintain at least 3 backup generations.
- Store at least one backup generation offsite.

### Retention Policies

```text
keep-daily=7
keep-weekly=4
keep-monthly=12
keep-yearly=2
```

Define retention based on recovery requirements:

- Daily backups retained for 7 days.
- Weekly backups retained for 4 weeks.
- Monthly backups retained for 12 months.
- Annual backups retained per compliance requirements.

### Snapshot Management

| Command | Description |
|:--------|:------------|
| `pct snapshot <vmid> <snapname>` | Create |
| `pct listsnapshot <vmid>` | List |
| `pct rollback <vmid> <snapname>` | Rollback |
| `pct delsnapshot <vmid> <snapname>` | Delete |

Best practices:

- Name snapshots descriptively: `pre-upgrade-2026-02-05`.
- Document snapshot purpose in description.
- Clean old snapshots regularly.
- Test rollback procedures quarterly.

### Recovery Testing

Backups without tested recovery procedures are worthless:

- Quarterly restore tests of critical containers.
- Document recovery time for each container class.
- Validate backup integrity through test restores, not just backup completion.
- Maintain runbooks for disaster recovery scenarios.

### Replication

Proxmox supports ZFS replication to other nodes:

```bash
pvesr create-local-job 101 target-node --schedule '*/15' --rate 50
```

Replication provides:

- Near-real-time data protection (RPO in minutes).
- Rapid failover capability.
- Reduced recovery time compared to backup restoration.

**Replication does not replace backups** — corrupted data replicates as readily as valid data.

---
[Back to Overview](./OVERVIEW.md)
