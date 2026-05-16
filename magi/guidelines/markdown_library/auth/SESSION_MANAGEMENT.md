# Session Management

### Session ID Generation

- **Use cryptographically secure RNG.** Session IDs must be at least 128 bits of entropy.
- **Regenerate the session ID after successful authentication** to prevent session fixation.

### Cookie Attributes for Session Cookies

```
Set-Cookie: sid=<id>; HttpOnly; Secure; SameSite=Lax; Path=/
```

| Attribute | Purpose |
|:----------|:--------|
| `HttpOnly` | Prevents JavaScript access |
| `Secure` | HTTPS only |
| `SameSite=Lax` (or `Strict`) | CSRF mitigation |
| `Path=/` (or most restrictive) | Limits scope |
| `Domain` | Omit unless cross-subdomain sharing required |

### Timeouts (Both Required)

| Type | Range |
|:-----|:------|
| Absolute timeout | 8-24 hours regardless of activity |
| Idle timeout | 15-60 minutes of inactivity |

Absolute timeout limits the exposure window for stolen sessions. Idle timeout limits the exposure window for abandoned sessions.

### Logout

**Both required:**
- Server-side: delete the session from the session store
- Client-side: clear the session cookie (expired date + empty value)

A logout that only clears the cookie leaves the session valid on the server for reuse if the cookie is captured.

### Session Invalidation on Credential Change

Invalidate all sessions for a user on password change, email change, or security-sensitive account modification. The user must re-authenticate on all devices after a credential change.

### Storage

- **Server-side storage** (Redis, database, encrypted in-memory store) is preferred — provides revocation and unlimited session-data capacity.
- **Client-side sessions** (encrypted cookies) acceptable for small payloads; cannot be revoked without a server-side blacklist; constrained by 4KB cookie limits.

---
[Back to Overview](./OVERVIEW.md)
