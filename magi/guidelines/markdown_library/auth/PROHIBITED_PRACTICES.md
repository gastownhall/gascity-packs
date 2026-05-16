# Prohibited Practices

### Never Do

- Store secrets in source code, configuration files in version control, Docker images, or client bundles
- Use the OAuth 2.0 Implicit flow (`response_type=token`); use Authorization Code + PKCE
- Use the Resource Owner Password Credentials flow for new integrations
- Accept JWTs with `alg: none`; configure libraries to reject `none` explicitly
- Read JWT claims without validating the signature first
- Store tokens in `localStorage` or `sessionStorage`
- Transmit tokens or API keys in URL query parameters
- Use the same secrets across development, staging, and production environments
- Hash passwords with MD5, SHA-1, SHA-256, or any non-memory-hard algorithm
- Register wildcard redirect URIs in IdP configurations
- Check role names directly in application code instead of checking permissions
- Rely on UI-level permission checks without API-level enforcement
- Use static IAM access keys or service account key files when managed identity / workload federation is available
- Default to allow when authentication or authorization systems are unavailable (fail open)
- Log passwords, tokens, session IDs, API keys, or secrets in any log output
- Omit CSRF protection on state-changing endpoints that use cookie authentication
- Issue tokens without expiration or with lifetimes exceeding 24 hours for access tokens
- Run shakedown against mocked IdPs, in-memory session stores, or unit-test fixtures
- Skip shakedown after a "small" callback URL or issuer-setting change

### Always Do

- Use Authorization Code + PKCE for all user-facing authentication flows
- Validate signature, `iss`, `aud`, `exp`, `iat` on every JWT before reading claims
- Issue access tokens with 5-60 minute lifetimes; use refresh tokens for session continuity
- Implement refresh-token rotation with reuse detection
- Include cryptographically random `state` parameter in every authorization request; verify on callback
- Register exact-match callback URLs per environment; no wildcards, no `localhost` in production
- Store all secrets in dedicated secret-management services; rotate on schedule
- Use managed identities for cloud-hosted workloads; eliminate static credentials
- Set `HttpOnly`, `Secure`, `SameSite` on all authentication cookies
- Regenerate session IDs after authentication
- Check granular permissions at the API layer for every protected operation
- Require MFA for all administrative accounts
- Hash passwords with Argon2id or bcrypt (cost 12+) with per-password salts
- Log all authentication and authorization events to tamper-resistant storage
- Scan repositories and artifacts for committed secrets; block merges on detection
- Run shakedown after every trigger condition in §15

---
[Back to Overview](./OVERVIEW.md)
