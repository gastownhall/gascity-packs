# Secrets Management in Pipelines

### Storage Rules

**Never store secrets** as plaintext values in:
- Pipeline YAML files
- Repository configuration files
- Dockerfiles
- Build scripts
- Any file committed to version control

Secrets live exclusively in:
- The CI platform's secret store
- An external secret manager (Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager)
- Injected at runtime via OIDC token exchange

### Log Masking

Mask secrets in pipeline logs. **Never run `env`, `printenv`, or `set -x` in production pipelines** — these dump all environment variables including secrets to the log. Custom outputs (debug logging, error messages, environment variable dumps) can leak secrets if not handled carefully.

### Minimum Stage Scope

Scope secrets to the minimum required access level:
- GitHub Actions: environment-scoped secrets with required reviewers
- GitLab CI: environment-scoped variables with protected flags

A deployment secret needed only in the deploy stage is not available to lint, test, or build stages. **This limits blast radius if a malicious PR or compromised dependency exfiltrates environment variables during earlier stages.**

### OIDC Federation Over Static Secrets

**Prefer OIDC federation over static secrets for cloud provider authentication.** GitHub Actions, GitLab CI, CircleCI, and Buildkite support OIDC token exchange with AWS, Azure, and GCP. The CI runner receives a short-lived, scope-limited token that expires after the job completes. **No secret to rotate, no secret to steal.**

### Fork PR Secrets

**Do not expose secrets to pull request workflows triggered by external contributors (forks).** Fork-based PRs run in an untrusted context. Secrets available to fork PR workflows can be exfiltrated by a malicious PR that modifies the pipeline to echo secrets. Use `pull_request_target` (GitHub) or equivalent patterns where secrets are needed, with extreme caution.

### Rotation Schedule

| Secret Type | Cadence |
|:------------|:--------|
| Deploy tokens | Quarterly |
| Registry credentials | Quarterly |
| Signing keys | Semi-annually |

**Rotation must be automated or scripted** — manual rotation across multiple repositories is error-prone and inevitably skipped.

### Audit Secret Access

Alert on:
- Secret access by unexpected workflows
- Secret access from unexpected branches
- Secret creation/modification events

---
[Back to Overview](./OVERVIEW.md)
