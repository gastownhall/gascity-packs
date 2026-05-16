# Cluster Lifecycle and Maintenance

### Upgrade Planning

| Step | Action |
|:----:|:-------|
| 1 | Review release notes for deprecations and breaking changes |
| 2 | Test upgrades in non-production cluster with representative workloads |
| 3 | Upgrade control plane first |
| 4 | Upgrade node pools with surge for faster updates with minimal disruption |
| 5 | Validate workloads post-upgrade |

Schedule during maintenance windows with reduced traffic.

### Node Pool Operations

```bash
kubectl cordon <node>
kubectl drain <node> --ignore-daemonsets
# perform maintenance
kubectl uncordon <node>
```

Respect pod disruption budgets during drain operations. Scale node pools rather than individual nodes for capacity changes.

### Cluster Autoscaler

| Parameter | Value |
|:----------|:------|
| Scale-down delay | 10 m to avoid thrashing |
| Max node count | Prevent runaway costs |
| `skip-nodes-with-local-storage` | `true` |
| `skip-nodes-with-system-pods` | `true` |

Configure scale-up: when pending pods cannot be scheduled. Configure scale-down: when nodes underutilized for sustained period.

### Maintenance Windows

Define maintenance windows for AKS planned maintenance:

- Separate windows for control plane and node pool updates.
- Schedule during low-traffic periods.
- Communicate maintenance windows to stakeholders.
- Monitor during and after maintenance for issues.

---
[Back to Overview](./OVERVIEW.md)
