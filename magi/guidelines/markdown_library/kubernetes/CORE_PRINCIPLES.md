# Core Principles

These guidelines define strict, operationally sound patterns for Kubernetes deployments with emphasis on Azure Kubernetes Service (AKS). The standards optimize for:

- **Declarative Configuration**: All cluster state exists in version-controlled manifests; `kubectl` imperative commands are for debugging, never for production changes.
- **Resource Determinism**: Every workload specifies requests and limits; the scheduler makes informed decisions and nodes remain stable under load.
- **Defense in Depth**: Network policies, pod security standards, RBAC, and workload identity combine to create layered security boundaries.
- **Observable by Default**: Metrics, logs, and traces are first-class concerns. A workload without observability is a workload you cannot operate.
- **Failure-Aware Design**: Pods are ephemeral. Applications handle restarts, node failures, and network partitions gracefully — design for cattle, not pets.

### Primary Rule: The Cluster Is Not a Pet

Clusters are disposable infrastructure. Node pools scale, upgrade, and recycle. Pods terminate without warning. Applications that depend on stable pod identity, local disk state, or long-lived connections without reconnection logic will fail. **Workloads must tolerate restarts, rescheduling, and infrastructure churn as normal operating conditions.**

### Secondary Rule: Manifests Are the Source of Truth

If it's not in Git, it doesn't exist. Cluster state derived from imperative commands (`kubectl apply` without version control, manual edits via dashboard) creates configuration drift, audit gaps, and recovery failures. Every resource — Deployments, Services, NetworkPolicies, RBAC bindings — is defined in versioned manifests and applied through automated pipelines.

### Azure Kubernetes Service Context

AKS provides managed control plane, Azure integration for identity and networking, and operational conveniences. These guidelines assume AKS unless explicitly noted, but core patterns apply to any conformant Kubernetes distribution. AKS-specific features (workload identity, Azure CNI, Key Vault integration) are preferred when they reduce operational burden without creating vendor lock-in for portable workloads.

### Kubernetes Version Policy

- Run current minor version minus one (N-1) for stability with security patch coverage.
- Upgrade within 30 days of new stable release availability.
- Test upgrades in non-production clusters before production rollout.
- Monitor deprecation warnings; address before forced removal in future versions.
- AKS auto-upgrade with maintenance windows is acceptable for non-critical clusters; critical clusters require controlled upgrade orchestration.

---
[Back to Overview](./OVERVIEW.md)
