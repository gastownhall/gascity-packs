# Role-Based Access Control

RBAC maps users to roles and roles to permissions. Authorization decisions check **permissions**, not roles directly. This indirection allows role definitions to evolve without changing authorization logic in application code.

### Check Permissions, Not Roles

```text
Correct:    if (user.hasPermission('orders:write')) { ... }
Incorrect:  if (user.role === 'admin') { ... }
```

Role-to-permission mapping lives in the IdP or a dedicated authorization service, not scattered across application code. When a role's permissions change, the authorization service updates — application code does not.

### Permission Granularity

Define permissions at the **resource + action** level:
- `orders:read`, `orders:write`, `orders:delete`
- `users:manage`
- `reports:export`

Coarse permissions (`admin`, `editor`, `viewer`) become insufficient as the application grows.

### Permission Delivery

| Strategy | Pros | Cons |
|:---------|:-----|:-----|
| Embedded in access token (custom claims) | Low latency | Cannot revoke mid-token-lifetime |
| Fetched from authz service per request | Always current | Per-request latency |

Choose based on the application's revocation requirements and latency budget.

### ABAC for Resource-Level Decisions

Combine RBAC for coarse access and **ABAC (attribute-based)** for fine-grained resource-level decisions:
- "User can edit orders" — RBAC
- "User can edit only their own orders" — ABAC
- "User can edit orders in their region" — ABAC

### Audit Role Assignments

Audit role assignments periodically. Remove roles from users who no longer need them (job change, project completion, offboarding). Automated role-review workflows reduce permission accumulation over time.

### API-Level Enforcement

**Apply authorization checks at the API/service layer, not only at the UI layer.** UI-level permission checks (hiding buttons, disabling menu items) improve user experience but provide zero security. A user with browser developer tools bypasses every UI-level check.

---
[Back to Overview](./OVERVIEW.md)
