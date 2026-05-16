# Filesystem and Mount Configuration

### Root Filesystem Types

| Type | Description |
|:-----|:------------|
| `dir` | Simple directory on the host. No snapshots, simplest configuration |
| `lvm` | Block device from LVM. Supports snapshots with thin provisioning |
| `zfs` | ZFS-native storage. Native snapshots, compression, checksumming |
| `rbd` | Ceph RADOS Block Device. Distributed storage with replication |

### Bind Mounts

```ini
mp0: /host/path,mp=/container/path,backup=1
```

| Parameter | Purpose |
|:----------|:--------|
| Path on host (absolute) | Source directory |
| `mp` | Mount point inside container |
| `backup` | Include in container backups (1) or exclude (0) |
| `ro` | Read-only mount |
| `acl` | Enable ACL support |
| `quota` | Enable quota support |

**Use cases:**

- Shared configuration files across containers.
- Large dataset access without copying into container storage.
- Log aggregation directories.

**Bind mount restrictions for unprivileged containers:**

- Host directories must be owned by the mapped UID range.
- Or use `shift` option for automatic UID shifting (requires `shiftfs` or idmapped mounts).

### Additional Volumes

```ini
mp1: local-lvm:32,mp=/var/lib/mysql,backup=1
mp2: nfs-share:subdir,mp=/data,shared=1,backup=0
```

Use additional volumes to:

- Separate application data from root filesystem.
- Place database storage on appropriate storage backend.
- Enable independent sizing and snapshot policies.

### Permissions and Ownership

Unprivileged container filesystem ownership considerations:

- Files created in container appear owned by mapped UIDs on host.
- Host backup tools see files owned by high UIDs (100000+).
- Bind mounts require correct host-side ownership or UID shifting.
- ZFS storage handles this natively; other backends may require manual ownership adjustment.

For bind mounts to work correctly in unprivileged containers:

```bash
chown -R 100000:100000 /host/path  # Assuming default mapping
```

Or use idmapped mounts in newer kernels to handle mapping automatically.

---
[Back to Overview](./OVERVIEW.md)
