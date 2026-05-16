# Authentication and Token Management

Zenfolio authentication produces an **opaque token string that grants full access to the authenticated user's account**. Two methods: plain-text (`AuthenticatePlain`) and challenge-response (`GetChallenge` + `Authenticate`). Both produce the same token type.

### Authentication Methods

| Method | Use |
|:-------|:----|
| **Challenge-response** (`GetChallenge` + `Authenticate`) | **Production**. Never transmits the password in cleartext, even over TLS. Client receives a challenge, hashes the password with the challenge salt using SHA-256, sends the hash. Protects against server-side request logging |
| **`AuthenticatePlain`** | Development and testing only. **Never in production**, even over TLS. The password appears in request bodies that may be logged by proxies, WAFs, or application-level request logging |

### Token Storage

**Store the authentication token server-side only.** The token is transmitted to Zenfolio via:

- `X-Zenfolio-Token` header.
- `zf_token` cookie.

**This token grants full account access** — gallery creation, photo deletion, access control modification. **Leaking this token to client-side JavaScript is equivalent to leaking the account password.** The server-side proxy holds the token; **client-side code never sees it**.

### Token Lifecycle

| Property | Value |
|:---------|:------|
| Expiry | ~24 hours |
| Proactive refresh | At 20-hour mark — re-authenticate **before** expiry rather than waiting for a 401 |
| Cache TTL | 20 hours in proxy memory (Redis or in-process variable) |

Store the token acquisition timestamp alongside the token. A background job or lazy refresh on the next API call handles renewal transparently. **Multiple concurrent API requests share the same token, not each authenticate independently.** Protect the cached token with the same security controls as the credentials themselves.

### Credentials Storage

**Store Zenfolio account credentials (username, password) in a secret management system** (Vault, AWS Secrets Manager, Azure Key Vault, environment variables in secure runtime config). **Never in:**

- Source code.
- Configuration files committed to version control.
- CI/CD pipeline definitions.
- Dockerfiles.

The server-side proxy reads credentials from the secret store at runtime to authenticate.

---
[Back to Overview](./OVERVIEW.md)
