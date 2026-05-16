# Security Hardening

### Pod Security Standards

| Profile | Use For |
|:--------|:--------|
| Privileged | System components requiring host access only |
| **Baseline** | Minimum for production workloads |
| **Restricted** | Required for high-security environments |

Enforce via namespace labels:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: payments
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

### Container Security Context

Every container specifies:

| Field | Required Value |
|:------|:---------------|
| `runAsNonRoot` | `true` |
| `readOnlyRootFilesystem` | `true` |
| `allowPrivilegeEscalation` | `false` |
| `capabilities.drop` | `[ALL]` |

Add specific capabilities only when documented requirement exists.

### Workload Identity

AKS workload identity federates Kubernetes service accounts with Azure AD managed identities. Pods authenticate to Azure services without storing credentials.

| Step | Action |
|:----:|:-------|
| 1 | Create Azure managed identity |
| 2 | Create Kubernetes service account with workload identity annotation |
| 3 | Establish federated credential linking identity to service account |
| 4 | Pods using service account authenticate as the managed identity |

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: workload-sa
  namespace: payments
  annotations:
    azure.workload.identity/client-id: "12345678-1234-1234-1234-123456789012"
```

This replaces pod identity (deprecated) and eliminates secrets for Azure service authentication.

### Image Security

- Pull images from private registries only; configure image pull secrets.
- Enforce image signature verification (Azure Container Registry content trust or admission controllers).
- Scan images for vulnerabilities in CI pipeline; fail on critical CVEs.
- Use digest-based image references for immutability: `image: registry.example.com/app@sha256:abc123...`.
- Prohibit `latest` tag; prohibit mutable tags in production.

### Secrets Encryption

Enable encryption at rest for secrets in etcd. AKS encrypts by default; verify configuration for self-managed clusters. Consider Azure Key Vault integration for secrets requiring HSM backing or centralized management.

---
[Back to Overview](./OVERVIEW.md)
