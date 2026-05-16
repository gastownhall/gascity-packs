# Deployment Strategies

### Rolling Update

Default strategy; progressively replaces old pods with new:

| Parameter | Purpose |
|:----------|:--------|
| `maxUnavailable` | Maximum pods unavailable during update |
| `maxSurge` | Maximum pods over desired count during update |

**Recommended for high availability:** `maxUnavailable: 0, maxSurge: 25%`.

### Blue-Green Deployment

Run two complete environments; switch traffic atomically:

1. Deploy new version alongside existing.
2. Validate new version.
3. Update service selector to point to new version.
4. Keep old version available for rapid rollback.

**Resource-intensive — requires 2× capacity during transition.**

### Canary Deployment

Route percentage of traffic to new version:

- Ingress controller traffic splitting or service mesh routing.
- Progressive rollout: **5% → 25% → 50% → 100%**.
- Automated rollback on error rate thresholds.

Requires sophisticated routing and observability to detect issues in canary population.

### GitOps Deployment

Declarative deployment from Git repository:

- Flux or ArgoCD continuously reconciles cluster state with Git.
- Pull request workflow for changes; review before merge.
- Automatic rollback by reverting Git commit.
- Audit trail in Git history.

Flux example:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: app-repo
  namespace: flux-system
spec:
  interval: 1m
  ref:
    branch: main
  url: https://github.com/example/app
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: app-deployment
  namespace: flux-system
spec:
  interval: 10m
  path: "./deploy/production"
  prune: true
  sourceRef:
    kind: GitRepository
    name: app-repo
```

**Preferred model for production deployments — eliminates imperative kubectl operations.**

### Pod Disruption Budgets

Required for all production deployments:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: app-pdb
  namespace: payments
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api
```

PDBs ensure voluntary disruptions (node drains, upgrades, autoscaler scale-downs) do not breach availability minimums.

---
[Back to Overview](./OVERVIEW.md)
