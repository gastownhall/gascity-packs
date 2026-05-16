# Hierarchical Configuration Design

### Configuration Layering (Precedence Order)

| Priority | Layer | Purpose |
|:---------|:------|:--------|
| 1 (lowest) | Compiled defaults | Hardcoded fallbacks in code |
| 2 | App Configuration unlabeled | Shared defaults across environments |
| 3 | App Configuration labeled | Environment-specific overrides |
| 4 | Key Vault references | Secret values |
| 5 (highest) | Environment variables | Runtime overrides for non-secrets |

This layering enables:
- Shared baseline configuration across environments
- Environment-specific overrides without duplication
- Emergency overrides via environment variables without configuration store changes
- Secure secret injection without application knowledge of Key Vault

### Key Vault References in App Configuration

Bridge configuration and secrets:

```json
{ "uri": "https://myvault.vault.azure.net/secrets/database-password" }
```

The App Configuration provider automatically resolves references when the application identity has Key Vault access. Applications see the resolved secret value; they need not know the secret's physical location.

Reference format includes optional version pinning:

| Form | URI |
|:-----|:----|
| Pinned (production stability) | `https://myvault.vault.azure.net/secrets/database-password/abc123def456` |
| Latest (auto-pickup) | `https://myvault.vault.azure.net/secrets/database-password` |

Pin versions for production stability; use versionless references for automatic rotation pickup in non-critical scenarios.

### Configuration Composition

```
Application/
├── Database/
│   ├── ConnectionString (Key Vault reference)
│   ├── CommandTimeout
│   ├── MaxPoolSize
│   └── RetryCount
├── Cache/
│   ├── ConnectionString (Key Vault reference)
│   ├── DefaultExpiration
│   └── SlidingExpiration
├── FeatureFlags/
│   ├── EnableNewCheckout
│   └── EnableBetaFeatures
└── Observability/
    ├── LogLevel
    ├── SamplingRate
    └── ExporterEndpoint
```

Load configuration sections selectively based on application components. A background worker need not load UI configuration; a web frontend need not load batch processing settings.

---
[Back to Overview](./OVERVIEW.md)
