# Core Principles

These guidelines define strict, secure, and operationally sound patterns for Azure App Configuration, Key Vault, and Azure resource parameterization, optimizing for:

- **Separation of Concerns**: Configuration values, feature flags, and secrets are distinct categories with different security requirements, lifecycles, and access patterns; treat them accordingly
- **Zero Secrets in Code**: No credentials, connection strings, or sensitive values appear in source control, environment variables at build time, or application binaries
- **Centralized Configuration**: Application configuration lives in a single authoritative source per environment; local overrides exist only for development scenarios
- **Least Privilege Access**: Every identity — human or service — receives only the permissions required for its function; broad access is never granted for convenience
- **Auditability**: Every configuration change and secret access is logged, attributable to an identity, and available for compliance review

### Primary Rule: Secrets and Configuration Are Different Things

App Configuration stores non-sensitive settings: feature flags, connection endpoints, timeout values, UI labels. Key Vault stores secrets: credentials, certificates, encryption keys, API tokens. The boundary is clear: **if disclosure of a value enables unauthorized access or violates compliance, it belongs in Key Vault. Everything else belongs in App Configuration.**

Mixing these categories — storing secrets in App Configuration or non-sensitive values in Key Vault — creates operational confusion, increases costs, and complicates access control. Use Key Vault references in App Configuration to bridge the two services when configuration needs to include secret values.

### Secondary Rule: Configuration Is Not Deployment

Configuration changes should not require application redeployment. Well-designed applications read configuration at startup and optionally refresh during runtime. The deployment artifact remains immutable; behavior varies through configuration. This separation enables feature toggles, A/B testing, gradual rollouts, and emergency configuration changes without release cycles.

### Sentinel Integration Philosophy

Microsoft Sentinel provides the security analytics layer for configuration and secret management. Diagnostic logs from App Configuration and Key Vault flow to Sentinel for threat detection, compliance monitoring, and incident response. **Sentinel is not optional for production workloads** — it is the mechanism that transforms audit logs into actionable security intelligence.

---
[Back to Overview](./OVERVIEW.md)
