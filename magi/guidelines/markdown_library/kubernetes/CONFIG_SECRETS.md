# Configuration and Secrets Management

### ConfigMaps

Use ConfigMaps for non-sensitive configuration:

- Application configuration files.
- Environment-specific settings.
- Feature flags.

Mount as files or inject as environment variables. Prefer file mounts for complex configuration; environment variables for simple key-value pairs.

### Secrets

Kubernetes secrets are base64 encoded, **not encrypted**. Treat secrets storage as sensitive:

- Enable etcd encryption at rest.
- Restrict secret access via RBAC.
- Use external secret stores for high-value secrets.

### External Secrets Operator

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: database-credentials
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: azure-keyvault
    kind: ClusterSecretStore
  target:
    name: database-credentials
  data:
  - secretKey: password
    remoteRef:
      key: database-password
```

Centralizes secret management while providing Kubernetes-native secret consumption.

### Azure Key Vault CSI Driver

Mount secrets as volumes using `SecretProviderClass`:

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: azure-keyvault-secrets
spec:
  provider: azure
  parameters:
    usePodIdentity: "false"
    useVMManagedIdentity: "true"
    tenantId: "tenant-id"
    keyvaultName: "keyvault-name"
    objects: |
      array:
        - |
          objectName: database-password
          objectType: secret
```

### Configuration Updates

ConfigMap and Secret updates do not automatically restart pods. Options:

- Volume mounts update automatically (with delay); applications must watch for changes.
- Reloader controller automatically triggers rolling updates on configmap/secret changes.
- GitOps pipelines modify deployment annotation to force rollout.

---
[Back to Overview](./OVERVIEW.md)
