# RBAC and Access Control

### Role Design

| Role | Scope | Permissions |
|:-----|:------|:------------|
| `cluster-admin` | Cluster | Full access (platform team only) |
| `namespace-admin` | Namespace | Full access within namespace |
| `developer` | Namespace | Deploy, view pods, access logs |
| `viewer` | Namespace | Read-only access |

### ClusterRole vs Role

- **ClusterRole** — cluster-scoped or reusable across namespaces.
- **Role** — namespace-scoped only.

Use ClusterRole with RoleBinding (not ClusterRoleBinding) to grant consistent permissions across multiple namespaces without cluster-wide access.

### Azure AD Integration

AKS integrates with Azure AD for authentication:

- Azure AD groups map to Kubernetes RBAC.
- Conditional access policies apply to cluster access.
- Privileged Identity Management (PIM) for just-in-time admin access.

Users authenticate via `az aks get-credentials` which obtains Azure AD tokens; kubeconfig does not contain static credentials.

### Service Accounts

Every workload uses a dedicated service account:

- Default service account should not have permissions beyond baseline.
- Disable automounting of service account tokens unless required: `automountServiceAccountToken: false`.
- Grant minimal permissions to service accounts via RoleBindings.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-sa
  namespace: payments
automountServiceAccountToken: false
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: app-role
  namespace: payments
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-binding
  namespace: payments
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: app-role
subjects:
- kind: ServiceAccount
  name: app-sa
  namespace: payments
```

---
[Back to Overview](./OVERVIEW.md)
