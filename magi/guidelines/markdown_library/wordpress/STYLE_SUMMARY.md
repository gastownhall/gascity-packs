# Style Summary

| Element | Required pattern |
|:--------|:-----------------|
| **PHP Standards** | `declare(strict_types=1)`; type all parameters and returns; PSR-4 autoloading for plugin internals; WordPress Coding Standards for public-facing code |
| **Security** | Sanitize input; escape output; nonce every mutation; capability-check every action; prepare every query; block XML-RPC; disable user enumeration |
| **wp-config.php** | `DISALLOW_FILE_EDIT`, `DISALLOW_FILE_MODS`, `FORCE_SSL_ADMIN` all `true`; `WP_DEBUG` `false` in production; unique salts; non-default table prefix |
| **Database** | `WP_Query` and `wpdb` exclusively; no SQL concatenation; prepare all parameterized queries; custom tables via `dbDelta` with schema versioning |
| **Transients** | Always set expiration; key under 172 chars; invalidate on data change; stampede protection for high-traffic caches |
| **REST API** | `permission_callback` on every route; validate and sanitize every arg; `WP_REST_Response` with status codes; rate limit auth endpoints |
| **Plugins** | Self-contained with declared dependencies; activation seeds schema; deactivation cleans cron; uninstall removes all data; named callbacks |
| **WooCommerce** | Declare HPOS compatibility; use `wc_get_orders`; verify webhook signatures; isolate sessions for headless; extend via documented interfaces |
| **Page Builders** | Child theme only; conditional assets per builder context; clear caches in deployment; single editor per page |
| **Performance** | Under 50 queries per frontend load; conditional enqueuing; audit autoloaded options; page cache compatibility; no unbounded queries |
| **Deployment** | Environment detection via `wp_get_environment_type()`; version-controlled custom code; Composer dependencies; forward-only migrations; CI/CD pipeline |
| **Cron** | `DISABLE_WP_CRON` with system replacement; idempotent callbacks; Action Scheduler for heavy loads; deregister on deactivation |
| **Shakedown** | Real staging matching production; six validation categories; WP-CLI canonical sequence; pass/fail-blocking/fail-nonblocking/inconclusive; four required artifacts |
| **Defense in Depth** | Staging + backups + update discipline + integrity monitoring + uptime monitoring + log aggregation + DNS/TLS monitoring = seven independent layers; uptime + integrity + verified backup = the Rule of Three quorum |

---

**Apply these guidelines universally to all WordPress development.**

---
[Back to Overview](./OVERVIEW.md)
