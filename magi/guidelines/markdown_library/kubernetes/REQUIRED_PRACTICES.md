# Required Practices

### Always Do

- Define resource requests and limits for every container.
- Use namespaces to isolate workloads with RBAC and NetworkPolicies.
- Configure liveness, readiness, AND startup probes appropriate to application behavior.
- Enable Pod Security Standards at namespace or cluster level.
- Store all manifests in version control; apply via GitOps or controlled pipelines.
- Use managed identity or workload identity for Azure service authentication.
- Configure pod disruption budgets for all production deployments.
- Apply NetworkPolicies implementing least-privilege network access.
- Enable audit logging for security and compliance visibility.
- Monitor resource utilization and adjust based on observed behavior.
- Test disaster recovery procedures regularly.
- Use private container registries with image scanning.
- Implement pod topology spread for zone redundancy.
- Configure appropriate node selectors and affinity for workload placement.
- Document cluster architecture, access patterns, and operational procedures.
- Run a §18 shakedown after every release that touches workload, network, storage, or RBAC surface.

---
[Back to Overview](./OVERVIEW.md)
