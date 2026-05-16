# Token Lifecycle Management

### Token Lifetime Targets

| Token Type | Lifetime | Notes |
|:-----------|:---------|:------|
| Access token (high-security app) | 5-15 minutes | Combine with refresh tokens |
| Access token (standard app) | 30-60 minutes max | Combine with refresh tokens |
| Refresh token (web app) | Hours, absolute max ~30 days | Rotation required |
| Refresh token (mobile app) | Days, absolute max ~30 days | Rotation required |

### Refresh Token Rotation

- **Issue a new refresh token with every access-token refresh** and invalidate the old one.
- **Detect and revoke the entire token family** if a previously-rotated refresh token is reused (indicates theft).

### Transmission

- **Transmit tokens exclusively over TLS.** Bearer tokens in `Authorization: Bearer {token}` must never traverse unencrypted connections.
- Enforce HTTPS at the infrastructure level (HSTS, redirect HTTP → HTTPS).

### Storage by Client Type

| Client | Storage |
|:-------|:--------|
| Server-side application | Encrypted server-side session or secure in-memory store |
| SPA | In-memory JavaScript variables — **never `localStorage`, never `sessionStorage`** |
| Mobile app | Platform secure storage (Keychain on iOS, Keystore on Android) |
| Cookies | `httpOnly`, `Secure`, `SameSite=Lax` or `Strict`, restrictive Path/Domain |

**`localStorage` and `sessionStorage` are forbidden for token storage** — accessible to any JavaScript on the page, including XSS payloads and compromised third-party scripts.

### Revocation

Implement token revocation for logout, password change, permission change, and security events:
- **JWTs (stateless)** — server-side blacklist checked per request, or rely on short expirations.
- **Opaque tokens** — delete from the token store.

### Sliding Window Expiration

Each successful refresh extends the token's lifetime by a fixed duration, up to an absolute maximum. Provides seamless experience for active users while ensuring inactive sessions expire.

### Token Refresh Patterns

- **Proactive refresh.** Schedule refresh at 75% of the access token's lifetime (e.g., at 45 seconds for a 60-second token). Do not wait for a 401.
- **Serialize refresh requests.** Multiple concurrent refresh attempts cause race conditions: one succeeds, rotating the refresh token, and the others fail because they present the now-invalidated old refresh token. Queue refresh requests and share the result.
- **Handle refresh failure gracefully.** If the refresh token is expired, revoked, or invalid, redirect to login. Clear stored tokens. Do not retry indefinitely.

---
[Back to Overview](./OVERVIEW.md)
