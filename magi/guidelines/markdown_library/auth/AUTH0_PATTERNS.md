# Auth0 Configuration Patterns

These patterns apply to Auth0 specifically; principles transfer to any managed IdP (Okta, Cognito, Firebase Auth).

### Tenant Strategy

- **Separate Auth0 tenants for development, staging, and production.** Tenant-level settings (signing keys, connections, rules, actions) differ across environments. A shared tenant risks dev changes affecting prod authentication.
- Register each application as a distinct Auth0 Application with its own `client_id`. Share clients only when they represent the same logical application in different deployment contexts.
- Configure allowed callback URLs, allowed logout URLs, and allowed web origins as exact-match values. **Remove `localhost` entries from production tenant configurations.**

### Auth0 Actions over Rules/Hooks

Use Auth0 Actions (`post-login`, `pre-registration`, `post-user-registration`) instead of deprecated Rules and Hooks. Actions execute in a Node.js runtime with explicit event/API contracts. Use Actions for:
- Custom claims enrichment
- Role assignment
- MFA step-up
- Access denial based on business logic

### Token Lifetime Configuration

| Application Type | Access Token TTL | Refresh Token Lifetime |
|:-----------------|:-----------------|:-----------------------|
| SPA | 300-900 seconds | With rotation enabled |
| Server-side app | 3600 seconds | With rotation enabled |
| Refresh token absolute max | — | 30 days (2,592,000 seconds) |

Enable refresh token rotation **and reuse detection**.

### Auth0 Organizations

Use Auth0 Organizations for B2B multi-tenant applications. Organizations isolate user pools, connections, and branding per customer. Prevents user identity leakage between tenants and enables per-organization SSO configuration.

### Configuration Storage

Store Auth0-specific configuration in runtime configuration:
- `domain`, `client_id`, `audience` — not secrets (appear in client-side code for SPAs) but must be environment-specific
- `client_secret` — in a secret manager

### ID Token Validation

Validate ID tokens from Auth0 with the same rigor as any JWT:
- Verify signature against `https://{domain}/.well-known/jwks.json`
- Check `iss` matches `https://{domain}/`
- Check `aud` matches the `client_id`
- Check `exp` and `iat`
- Verify `nonce` if one was sent in the authorization request

---
[Back to Overview](./OVERVIEW.md)
