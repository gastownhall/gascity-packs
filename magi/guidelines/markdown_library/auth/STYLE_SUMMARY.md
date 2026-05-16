# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Core | Zero trust; least privilege; fail closed; defense in depth; secrets are liabilities to minimize |
| Secrets | Vault/KMS storage; per-environment isolation; scheduled rotation; dual-secret for zero-downtime; audit access; scan for leaks |
| OAuth/OIDC | Authorization Code + PKCE mandatory; implicit and ROPC prohibited; `state` for CSRF; exact-match callbacks; minimum scopes |
| JWT | Validate signature before claims; reject `alg: none`; verify `iss`/`aud`/`exp`/`iat`/`nbf`; asymmetric algorithms for shared tokens; cache JWKS with `kid`-based invalidation |
| Tokens | Access 5-60 min; refresh with rotation and reuse detection; `HttpOnly` cookies or in-memory; never `localStorage`; proactive refresh at 75% lifetime; revoke on logout/password change |
| Sessions | Cryptographic IDs (≥128 bits); regenerate on auth; `HttpOnly`+`Secure`+`SameSite` cookies; absolute and idle timeouts; server-side storage for revocability |
| Auth0 | Separate tenants per env; exact callback URLs; Actions over Rules; token lifetimes per app type; Organizations for B2B; validate ID tokens fully |
| RBAC | Check permissions not roles; `resource:action` granularity; API-level enforcement mandatory; ABAC for resource-level decisions; audit role assignments |
| MFA | Required for admins; prefer WebAuthn over TOTP over SMS; step-up for sensitive operations; recovery codes as single-use secrets |
| CSRF | Synchronizer token or double-submit; `SameSite=Lax` on auth cookies; validate `Origin`/`Referer`; required for all cookie-authenticated mutations |
| Passwords | Argon2id or bcrypt; unique salt per password; 12+ char minimum; no composition rules; check breach databases; never log plaintext |
| Cloud Auth | Managed identity for hosted workloads; workload federation for external; OIDC for cross-cloud; minimum-scope IAM roles; CloudTrail/Audit Logs enabled |
| API Auth | Keys in headers not URLs; hash keys before storage; per-key rate limiting; mTLS or short-lived tokens for service-to-service |
| Audit | Log all auth events; log all authz failures; alert on anomalies; tamper-resistant storage; never log credentials |
| Shakedown | Real IdP sandbox + real JWKS + real session store + real MFA verifier; eight categories; classified outcome |
| Defense in Depth | Vetted libraries + rate limits + MFA + session rotation + audit + anomaly detection + revocation + shakedown |

---

Following these rules produces authentication and authorization systems that are correct under attack, recoverable under failure, and auditable under compliance. Identity is the security boundary; secrets are the attack surface; defense in depth is the resilience strategy. Every shortcut is a vulnerability; every "small" auth change without shakedown is a future incident.

**Apply this guidance universally to every system that authenticates users, services, or systems across the organization.**

---
[Back to Overview](./OVERVIEW.md)
