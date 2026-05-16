# Secrets Management

Secrets management governs how credentials, keys, certificates, and tokens are stored, accessed, rotated, and revoked across all environments. A compromised secret grants the attacker the identity and permissions of the secret's owner.

### Storage

**Never store secrets in source code, configuration files committed to version control, CI/CD pipeline definitions, Docker images, client-side bundles, or log output.** Secrets live in dedicated secret stores:

- Environment variables (for containers)
- Secret management services: HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager
- Encrypted configuration injected at deployment time

### Rotation Schedule

| Secret Type | Minimum Rotation Cadence |
|:------------|:-------------------------|
| API keys | Quarterly |
| Signing keys | Semi-annually |
| Database credentials | Quarterly |
| Certificates | Before expiry with 30-day buffer |
| Service account keys | Prefer automatic rotation via managed identity |

Rotate immediately on suspected compromise.

### Per-Environment Isolation

**Use distinct secrets per environment.** Development, staging, and production must never share API keys, signing secrets, database credentials, or encryption keys. A compromised development secret must not grant production access.

### Dual-Secret Rotation (Zero-Downtime)

For zero-downtime key changes:

1. Deploy the new secret alongside the old
2. Update all consumers
3. Verify no service uses the old secret
4. Revoke the old secret

Verification must be automated — manual checks miss services.

### Audit Secret Access

Secret stores must log every read, write, and delete operation with the identity of the accessor, timestamp, and accessed secret identifier. Alert on anomalous access patterns:
- Access from unexpected IPs
- Access outside business hours
- Bulk secret reads

### Prefer Managed Identities

Prefer managed identities over static secrets for cloud service authentication. **Azure Managed Identity, AWS IAM Roles for EC2/ECS/Lambda, and GCP Service Account impersonation with Workload Identity eliminate static credentials entirely.** No secret to rotate means no secret to compromise.

### Encryption

Encrypt secrets at rest in the secret store and in transit between the store and the consumer. TLS for network transit. AES-256 or equivalent for storage encryption. Key management for the encryption keys themselves must follow the same rigor — encrypting secrets with a hardcoded key is not encryption.

### Secret Scanning

Scan repositories and CI/CD artifacts for accidentally committed secrets using automated tools (`gitleaks`, `trufflehog`, GitHub secret scanning). Run on every commit and PR. **Block merges when secrets are detected.** Remediate by rotating the exposed secret immediately, not by deleting the commit (git history retains the secret).

---
[Back to Overview](./OVERVIEW.md)
