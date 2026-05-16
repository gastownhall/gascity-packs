# Secret and Credential Management

Secrets are the most dangerous category of configuration. Mishandled secrets enable unauthorized access, data breaches, and compliance violations. Self-healing automation handles secrets with extreme care.

### Secret Sources

- **Environment variables** — Standard for containerized deployments. Process-scoped. Not persisted to disk. Visible in process listings on some systems.
- **Secret files** — Mounted volumes containing credential data. Container orchestrators (Kubernetes) provide secret mounting. Set restrictive permissions (0400).
- **Secret management services** — HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager. Provide audit logging, rotation, and access control.
- **Interactive prompts** — Request credentials from operators at runtime. Never echo input. Timeout prompts to prevent hanging.

### Secret Handling Rules

- **Never log secrets** — Not in messages, not in debug output, not in error dumps.
- **Never persist secrets to disk** — Except in designated secret storage. No temporary files containing credentials. No configuration files with embedded secrets.
- **Never embed secrets in code** — Not even "for testing." Source control has memory. Secrets in code become secrets in public.
- **Clear secrets after use** — Zero memory containing secrets when finished. Unset environment variables after reading.
- **Validate secrets before use** — Malformed credentials waste time with auth failures. Validate format before attempting authentication.

### SSH and Remote Access

- **Key-based authentication** — Preferred. No passwords to manage. Keys can be rotated and revoked.
- **SSH agent forwarding** — For operations requiring access to multiple hosts. Be aware of security implications on untrusted hosts.
- **`sshpass` for password authentication** — When key-based auth is unavailable, use `sshpass` with `-f` (file) or `-e` (environment). **Never use `-p`** with the password as an argument — it appears in process listings.
- **Host key verification** — Disable only when absolutely necessary and only for known, controlled hosts. Disabling universally enables MITM attacks.

### Credential Rotation

Automation must handle credential rotation without downtime:
- Detect authentication failures that indicate rotated credentials
- Refresh credentials from authoritative sources
- Retry operations with refreshed credentials
- Alert when credentials cannot be refreshed

---
[Back to Overview](./OVERVIEW.md)
