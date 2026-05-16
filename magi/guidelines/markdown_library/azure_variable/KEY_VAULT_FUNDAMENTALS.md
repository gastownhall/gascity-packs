# Key Vault Fundamentals

### Service Purpose

Azure Key Vault provides secure storage for secrets, certificates, and cryptographic keys. It is the only appropriate location for:

- Database credentials and connection strings with embedded passwords
- API keys and tokens for external services
- Certificates for TLS, code signing, and authentication
- Encryption keys for data protection
- Service principal credentials

### Vault Types

| Type | Use Case | Protection |
|:-----|:---------|:-----------|
| Standard | Most workloads | Software |
| Premium | Compliance requirements (FIPS 140-2 Level 2+) | HSM-backed |
| Managed HSM | Highest security; dedicated HSM pool | Dedicated HSM |

Select Standard for typical applications. Upgrade to Premium only when compliance mandates HSM protection.

### Secret Lifecycle

Secrets have explicit lifecycles:

- **Enabled / Disabled** — Toggle availability without deletion
- **Activation Date** (optional) — Secret unavailable before this timestamp
- **Expiration Date** (required) — Secret unavailable after this timestamp; triggers rotation alerts
- **Version** — Each update creates a new version; previous versions remain accessible by version ID

**Set expiration dates on all secrets.** Unexpired secrets without rotation schedules represent security debt.

### Secret Naming

Names follow a constrained pattern:
- Alphanumeric characters and hyphens only
- Maximum 127 characters
- No path separators (Key Vault has no hierarchy)

Convention:

```
{application}-{environment}-{purpose}
```

Examples:
- `orderservice-prod-dbpassword`
- `orderservice-prod-stripeapikey`
- `shared-prod-sendgridkey`

Wrong: `prod_db_password` (underscores not allowed; missing application).

### Certificate Management

Key Vault manages certificate lifecycle:
- Store certificates with private keys
- Automatic renewal for certificates issued by integrated CAs
- Manual renewal notifications for externally issued certificates
- Certificate policy enforcement (key type, validity period, subject)

### Key Management

Cryptographic keys in Key Vault support:
- Encryption/decryption operations without key export
- Signing/verification for JWT and document signing
- Key wrapping for envelope encryption patterns

**Keys never leave Key Vault for operations; data travels to the key.** This architecture prevents key exposure even to application code.

---
[Back to Overview](./OVERVIEW.md)
