# CSRF Protection

CSRF exploits the browser's automatic credential inclusion (cookies) to make authenticated requests on behalf of a user without their knowledge. **CSRF protection is required for every state-changing request that uses cookie-based authentication.**

Stateless APIs that authenticate solely via `Authorization` headers (Bearer tokens) are inherently CSRF-resistant — browsers do not attach `Authorization` headers automatically.

### Defense Mechanisms

Both are effective; choose based on application architecture:

- **Synchronizer Token Pattern** — server-generated CSRF token embedded in forms and validated on submission.
- **Double-Submit Cookie Pattern** — CSRF token in both a cookie and a request header/body; server validates they match.

### Cookie SameSite

Set `SameSite=Lax` (recommended default) or `SameSite=Strict` on all authentication cookies:
- `Lax` prevents cross-site POST requests from including the cookie (mitigates most CSRF)
- `Strict` prevents all cross-site cookie inclusion (may break legitimate cross-site navigation)

### Origin/Referer Validation

Validate `Origin` and `Referer` headers on state-changing requests as a defense-in-depth measure. Reject requests where `Origin` does not match the expected domain.

---
[Back to Overview](./OVERVIEW.md)
