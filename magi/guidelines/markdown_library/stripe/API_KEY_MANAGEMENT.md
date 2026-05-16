# API Key Management

### Key Types

| Key | Prefix | Use |
|:----|:-------|:----|
| Publishable | `pk_test_*`, `pk_live_*` | Client-side Stripe.js initialization |
| Secret | `sk_test_*`, `sk_live_*` | Server-side API calls |
| Restricted | `rk_test_*`, `rk_live_*` | Scoped permissions for specific services |
| Webhook signing secret | `whsec_*` | Verify webhook payloads |

Each key type has a strict usage boundary. **Crossing boundaries is a security violation.**

- **Secret keys (`sk_*`) exist only on the server.** Never embed in client-side code, mobile apps, CI logs, error messages, URLs, or version control. Exposure of a secret key grants full API access to the Stripe account.
- **Publishable keys (`pk_*`) are safe for client-side embedding.** They can only create tokens and confirm payments — they cannot read customer data, issue refunds, or modify account settings.

### Environment Separation

Test keys (`pk_test_*`, `sk_test_*`) and live keys (`pk_live_*`, `sk_live_*`) **must never coexist** in the same environment configuration:

- Development and staging use **test keys exclusively**.
- Production uses **live keys exclusively**.
- The application code references the variable name (`STRIPE_SECRET_KEY`), not the key value.

| Concern | Practice |
|:--------|:---------|
| CI/CD | Test keys for integration tests; live keys injected only at production deployment via secret management (Vault, AWS Secrets Manager, Azure Key Vault) |
| Startup validation | Validate the key prefix matches the expected environment; halt with explicit error if a staging server loads `sk_live_*` |
| Restricted keys | Use restricted keys for services that need limited Stripe access — webhook processing service needs only event retrieval, not charge creation |

### Key Rotation

Stripe supports rolling key rotation: generate a new key while the old key remains valid for a grace period.

- Rotate keys on a **quarterly minimum** schedule and immediately on suspected compromise.
- Update all consuming services during the grace period.
- Verify no service uses the old key before expiring it.
- **Webhook signing secrets rotate independently** of API keys — update the verification logic in all webhook consumers simultaneously, or support verifying against both old and new secrets during the transition window.

---
[Back to Overview](./OVERVIEW.md)
