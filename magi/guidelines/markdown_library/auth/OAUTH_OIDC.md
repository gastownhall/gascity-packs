# OAuth 2.0 and OpenID Connect

OAuth 2.0 provides delegated authorization. OpenID Connect (OIDC) adds an identity layer on top of OAuth 2.0. Together they form the foundation for user authentication and API authorization in modern applications. All implementations target **OAuth 2.1 draft alignment**: PKCE required, implicit flow prohibited, bearer tokens over TLS only.

### Flow Selection

| Flow | Use Case | Status |
|:-----|:---------|:-------|
| **Authorization Code + PKCE** | All user-facing authentication (web, SPA, mobile, CLI) | Required |
| **Client Credentials** | Service-to-service (machine-to-machine), no user context | Required for M2M |
| Implicit (`response_type=token`) | — | **Prohibited** |
| Resource Owner Password Credentials (ROPC) | Legacy only | **Prohibited for new** |

**Implicit flow is forbidden.** It exposes tokens in URL fragments, browser history, referrer headers, and server logs. It provides no refresh tokens and no code-exchange protection.

**ROPC is forbidden for new integrations.** It requires the application to handle raw user passwords, defeating the purpose of delegated authentication. Migrate existing ROPC to Authorization Code + PKCE.

**Client Credentials is for service-to-service only.** Never use Client Credentials for user-facing flows.

### Client Type Distinction

| Client Type | Description | Credential |
|:------------|:------------|:-----------|
| Public | SPAs, mobile apps, any client-side code | PKCE only (cannot store `client_secret`) |
| Confidential | Server-side web apps, backend services | `client_secret` server-side only |

### PKCE Implementation

PKCE adds a cryptographic challenge to the authorization-code exchange, binding the token request to the authorization request:

```text
1. Generate code_verifier (43-128 chars, URL-safe, cryptographically random)
2. Compute code_challenge = BASE64URL(SHA256(code_verifier))
3. Send code_challenge + code_challenge_method=S256 with authorization request
4. Send code_verifier with token request
5. IdP verifies SHA256(verifier) == challenge
```

Rules:
- **Use `S256` as the `code_challenge_method`.** The `plain` method transmits the verifier in the authorization request, providing no security benefit.
- Generate the `code_verifier` using a cryptographically secure RNG (`crypto.randomBytes`, `crypto.getRandomValues`, `os.urandom`). Predictable verifiers defeat PKCE entirely.

### State Parameter and CSRF Protection

The `state` parameter prevents CSRF attacks against the OAuth callback endpoint:

- Include a cryptographically random, unguessable `state` parameter in every authorization request
- Store `state` server-side (or in encrypted cookie / SPA in-memory store) before redirect
- Verify the returned `state` matches the stored value exactly; reject mismatches
- **`state` is single-use** — delete it after verification to prevent replay
- For stateless CSRF protection, encode context (return URL, flow type) in a signed/encrypted `state` payload and verify before trusting

### Callback URL Security

- **Register callback URLs as exact-match values** in the IdP configuration. No wildcards (`https://*.example.com/callback`).
- Do not use `localhost` in production registrations.
- Each environment registers its own callback URLs.
- Validate the `redirect_uri` on both authorization request and token exchange. The token endpoint must reject mismatches.
- **HTTPS only** in non-local environments. The single exception is `http://localhost` for local development.

### Scope Management

- Request `openid` scope for OIDC authentication. Add `profile` and `email` only when needed.
- **Do not request scopes "just in case."** Excessive scope requests trigger consent fatigue and reduce trust.
- Define custom API scopes for fine-grained authorization (`read:orders`, `write:products`, `admin:users`).
- Validate scopes on every API request, not just at token issuance.

---
[Back to Overview](./OVERVIEW.md)
