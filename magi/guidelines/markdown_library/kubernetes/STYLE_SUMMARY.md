# Style Summary

| Element | Required Configuration |
|:--------|:-----------------------|
| API Version | Use stable/v1 APIs; avoid alpha/beta in production |
| Namespaces | Logical isolation with quotas, limit ranges, and NetworkPolicies |
| Deployments | Explicit replicas, resources, probes, and security context |
| Resources | Requests AND limits mandatory; no BestEffort QoS in production |
| Probes | Liveness + readiness + startup all declared |
| Images | Pinned digests or immutable tags; private registry with scanning |
| Security Context | Non-root, read-only filesystem, dropped capabilities |
| Network Policies | Default deny with explicit allow rules |
| Secrets | External secret store integration; encrypted at rest |
| Ingress | TLS mandatory; rate limiting; WAF for public endpoints |
| RBAC | Least privilege; Azure AD integration; no default service account permissions |
| Service Accounts | Dedicated SA per workload; `automountServiceAccountToken: false` unless required |
| Observability | Metrics, logs, and traces; structured JSON logging; actionable alerts |
| Deployment Strategy | Rolling update with PDB; GitOps for production changes |
| Helm | Chart.yaml, values.schema.json, README.md, NOTES.txt; `--atomic` upgrades |
| Node Pools | Sized appropriately; multi-zone distribution; cluster autoscaler configured |
| Backup | Velero scheduled backups; recovery tested regularly |
| Version Policy | N-1 Kubernetes version; timely upgrades with testing |
| Shakedown | Real cluster + in-cluster Job + rollout/events/describe artifacts; classify pass / fail-blocking / fail-nonblocking / inconclusive |
| Defense in Depth | Probes + replicas + PDB + topology spread + resources + autoscale + observability |
| Rule of Three | Three replicas across three failure domains for Deployments and leader-elected components |

---
[Back to Overview](./OVERVIEW.md)
