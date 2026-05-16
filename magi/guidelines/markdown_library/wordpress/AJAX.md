# AJAX Patterns

### Admin AJAX Patterns

Register AJAX handlers with:

| Hook | Use |
|:-----|:----|
| `wp_ajax_{action}` | Authenticated |
| `wp_ajax_nopriv_{action}` | Unauthenticated |

- Verify nonces with `check_ajax_referer()`.
- Verify capabilities with `current_user_can()`.
- Return responses via `wp_send_json_success()` or `wp_send_json_error()`.
- Always call `wp_die()` at the end of the handler (the `wp_send_json` functions do this automatically).
- For unauthenticated endpoints, **apply rate limiting and input validation with the same rigor as public REST routes**.

### AJAX vs REST API Decision

**Prefer the REST API over `admin-ajax.php` for new development.** The REST API provides built-in schema validation, standardized authentication, HTTP method semantics, and cacheable GET endpoints. **`admin-ajax.php` routes all requests through a single endpoint (POST to `admin-ajax.php`), which defeats HTTP caching and complicates load balancer rules.** Reserve `admin-ajax.php` for backward-compatible integrations with legacy code or third-party plugins that expect it.

---
[Back to Overview](./OVERVIEW.md)
