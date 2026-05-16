# Kubernetes Library

These guidelines define strict, operationally sound patterns for Kubernetes deployments with emphasis on Azure Kubernetes Service (AKS), optimizing for declarative configuration, resource determinism, defense in depth, observability by default, and failure-aware design.

## Critical Mandates (Read First)
- **The Cluster Is Not a Pet** — workloads must tolerate restarts, rescheduling, and infrastructure churn.
- **Manifests Are the Source of Truth** — if it's not in Git, it doesn't exist.
- **Resource Requests AND Limits** mandatory for every container.
- **All Three Probe Types** (liveness + readiness + startup) declared per workload.
- **Default Deny NetworkPolicies** with explicit allow rules.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Cluster Architecture and Sizing](./CLUSTER_ARCHITECTURE.md)
3. [Namespace Strategy](./NAMESPACE_STRATEGY.md)
4. [Workload Configuration](./WORKLOAD_CONFIGURATION.md)
5. [Resource Management](./RESOURCE_MANAGEMENT.md)
6. [Health Probes](./HEALTH_PROBES.md)
7. [Networking](./NETWORKING.md)
8. [Storage Configuration](./STORAGE.md)
9. [Security Hardening](./SECURITY_HARDENING.md)
10. [Configuration and Secrets Management](./CONFIG_SECRETS.md)
11. [Ingress and Service Mesh](./INGRESS_SERVICE_MESH.md)
12. [Observability](./OBSERVABILITY.md)
13. [RBAC and Access Control](./RBAC.md)
14. [Deployment Strategies](./DEPLOYMENT_STRATEGIES.md)
15. [Helm Charts](./HELM_CHARTS.md)
16. [Cluster Lifecycle and Maintenance](./CLUSTER_LIFECYCLE.md)
17. [Disaster Recovery](./DISASTER_RECOVERY.md)
18. [Shakedown — Post-Deploy Validation](./SHAKEDOWN.md)
19. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
20. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
21. [Required Practices](./REQUIRED_PRACTICES.md)
22. [Style Summary](./STYLE_SUMMARY.md)
