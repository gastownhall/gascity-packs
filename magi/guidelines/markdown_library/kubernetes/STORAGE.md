# Storage Configuration

### Storage Classes

| Class | Use Case | Performance | Redundancy |
|:------|:---------|:------------|:-----------|
| `managed-premium` | Databases, high IOPS | High (SSD) | LRS/ZRS |
| `managed-standard` | General workloads | Moderate | LRS/ZRS |
| `azurefile-premium` | Shared storage (RWX) | Moderate | LRS/ZRS |
| `azure-disk-csi` | Block storage | Variable | Configurable |

### Persistent Volume Claims

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: database-storage
spec:
  accessModes:
  - ReadWriteOnce
  storageClassName: managed-premium
  resources:
    requests:
      storage: 100Gi
```

### Volume Expansion

Enable in storage class with `allowVolumeExpansion: true`. Expanding PVCs requires filesystem support and may require pod restart. **Shrinking is not supported** — size correctly from the start.

### StatefulSet Storage

StatefulSets use `volumeClaimTemplates` for per-replica storage:

- Storage persists through pod restarts and rescheduling.
- Storage bound to pod ordinal: `data-db-0`, `data-db-1`.
- Deleting StatefulSet does not delete PVCs; manual cleanup required.

### Ephemeral Storage

Use `emptyDir` for temporary scratch space:

- Deleted when pod terminates.
- Shared between containers in pod.
- Backed by node disk or memory (`medium: Memory`).

Set ephemeral storage limits to prevent pods from filling node disks:

```yaml
resources:
  limits:
    ephemeral-storage: 2Gi
```

---
[Back to Overview](./OVERVIEW.md)
