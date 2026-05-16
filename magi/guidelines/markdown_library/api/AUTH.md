# Authentication and Authorization

### Authentication Methods

**API Keys**: Simple, suitable for server-to-server communication where key secrecy is manageable. Transmit in header, not URL:
```
X-API-Key: sk_live_abc123
```
Security:
- Rotate regularly
- Scope to specific permissions
- Never commit to source control

**OAuth 2.0 / OpenID Connect**: Industry standard for user-delegated access:

| Flow | Use case |
|:-----|:---------|
| Authorization Code | Web applications |
| Client Credentials | Service accounts |
| Implicit (deprecated) | Legacy SPAs only |
| PKCE | Modern SPAs and mobile |

```
Authorization: Bearer eyJhbGc...
```

**JWT Bearer Tokens**: Stateless authentication with embedded claims. Validate every request:

- Verify **signature** with the issuer's public key
- Check **`iss`** (issuer) matches expected
- Check **`aud`** (audience) matches expected
- Verify **`exp`** (expiration) has not passed
- Check **`nbf`** (not-before) is in the past

Use short-lived access tokens with refresh tokens.

### Token Transmission

- Send tokens in `Authorization` header with `Bearer` scheme
- **Never accept tokens in URL query parameters** (logged, cached, visible)
- Never accept tokens in cookies for APIs (CSRF risk; cookies are for browser sessions, not API auth)
- Set appropriate token expiration

### Authorization Patterns

- **Role-Based Access Control (RBAC)**: Assign permissions to roles; assign roles to users
- **Attribute-Based Access Control (ABAC)**: Evaluate policies against request attributes
- **Resource-Based Authorization**: Permission checks against specific resource instances

Implement authorization checks at the API gateway **and** within services. Defense in depth prevents gateway bypass from exposing resources.

### Security Response Codes

- **401 Unauthorized**: No valid authentication provided (missing, expired, or invalid token)
- **403 Forbidden**: Valid authentication but insufficient permissions for this resource/action
- Include `WWW-Authenticate` header with 401 responses to indicate expected authentication scheme

---
[Back to Overview](./OVERVIEW.md)
