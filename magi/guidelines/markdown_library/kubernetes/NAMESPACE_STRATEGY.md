# Namespace Strategy

### Namespace Purpose

Namespaces provide logical isolation, RBAC boundaries, resource quota enforcement, and network policy scope. They are **not security boundaries** — pods in different namespaces share the cluster network by default until network policies enforce segmentation.

### Naming Convention

- Environment prefix where clusters span environments: `prod-`, `staging-`, `dev-`.
- Application or team ownership: `payments`, `user-service`, `platform-team`.
- Avoid generic names: `app`, `service`, `backend` provide no operational value.

### Standard Namespace Structure

| Namespace | Purpose | Access |
|:----------|:--------|:-------|
| `kube-system` | Cluster components | Platform team only |
| `ingress-system` | Ingress controllers, external-dns | Platform team only |
| `monitoring` | Prometheus, Grafana, alerting | Platform team; read for developers |
| `cert-manager` | Certificate management | Platform team only |
| `flux-system` or `argocd` | GitOps controllers | Platform team only |

Application namespaces created per-service or per-team based on organizational structure.

### Resource Quotas

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: compute-quota
  namespace: payments
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    persistentvolumeclaims: "10"
    services.loadbalancers: "2"
```

Quotas enforce capacity planning discipline and prevent runaway resource consumption from affecting other namespaces.

### Limit Ranges

Set defaults for pods that don't specify resources:

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: payments
spec:
  limits:
  - default:
      cpu: 500m
      memory: 512Mi
    defaultRequest:
      cpu: 100m
      memory: 128Mi
    type: Container
```

LimitRange prevents pods without resource specifications from scheduling unbounded — but **explicit specification in manifests remains required**.

---
[Back to Overview](./OVERVIEW.md)
