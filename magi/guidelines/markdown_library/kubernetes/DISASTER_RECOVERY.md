# Disaster Recovery

### Backup Scope

Kubernetes backup includes:

- Cluster resource definitions (Deployments, Services, ConfigMaps, Secrets).
- Persistent volume data.
- Custom resource definitions and instances.

Control plane state (etcd) is managed by AKS; focus on workload-level backup.

### Velero Configuration

```yaml
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: daily-backup
  namespace: velero
spec:
  schedule: "0 2 * * *"
  template:
    includedNamespaces:
    - "*"
    excludedNamespaces:
    - kube-system
    - kube-public
    - kube-node-lease
    storageLocation: azure-backup
    ttl: 720h0m0s
    volumeSnapshotLocations:
    - azure-disk
```

| Backup | Frequency |
|:-------|:----------|
| Full cluster | Daily |
| Critical namespace | Hourly |
| Volume snapshots | Aligned with backup schedule |

### Recovery Testing

| Scope | Frequency |
|:------|:----------|
| Critical namespaces | Monthly |
| Full cluster | Quarterly |

- Document recovery time for different failure scenarios.
- Maintain runbooks for common recovery procedures.

### Multi-Cluster Strategy

For critical workloads requiring geographic redundancy:

- **Active-passive** — secondary cluster on standby; failover during primary failure.
- **Active-active** — both clusters serve traffic; traffic management handles distribution.
- Replicate state via application-level replication or storage replication.

Multi-cluster adds significant complexity; validate requirement before implementing.

---
[Back to Overview](./OVERVIEW.md)
