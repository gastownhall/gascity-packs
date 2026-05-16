# Security

### Input Sanitization

**Sanitize on input.** Every value from `$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE`, and `$_SERVER` passes through an appropriate sanitization function before storage or processing.

| Function | Use |
|:---------|:----|
| `sanitize_text_field()` | Plain text |
| `sanitize_email()` | Email addresses |
| `sanitize_url()` | URLs (display) |
| `sanitize_file_name()` | File names |
| `absint()` | Non-negative integers |
| `wp_kses()` / `wp_kses_post()` | Rich content with allowed tags |

**Use the most restrictive sanitizer that fits the data type.** Never sanitize with a generic trim-and-strip approach when a purpose-built sanitizer exists.

**Never access `$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE`, or `$_SERVER` values directly without sanitization.** Use the WordPress-provided sanitization functions or validate with a whitelist of acceptable values.

### Output Escaping

**Escape on output.** Every dynamic value rendered into HTML, attributes, URLs, or JavaScript passes through the appropriate escaping function **at the point of output, not before storage**. Storing pre-escaped data creates double-escaping bugs and prevents safe reuse in different contexts.

| Context | Function |
|:--------|:---------|
| HTML content | `esc_html()` or `wp_kses_post()` for rich content |
| HTML attribute | `esc_attr()` |
| URL (`href`/`src`) | `esc_url()` for output; `esc_url_raw()` for database storage and redirects |
| JavaScript | `esc_js()` for inline script values; `wp_json_encode()` for `wp_localize_script` / `wp_add_inline_script` |
| SQL | `$wpdb->prepare()` with typed placeholders (`%s`, `%d`, `%f`) |

### Nonce Verification

**Every form submission, AJAX request, and state-changing REST API call from the WordPress admin must include and verify a nonce.** Nonces prevent CSRF attacks.

| Context | Generate | Verify |
|:--------|:---------|:-------|
| Form | `wp_nonce_field()` | `check_admin_referer()` |
| AJAX | `wp_create_nonce()` | `check_ajax_referer()` |
| REST | `X-WP-Nonce` header with `wp_rest` nonce | `permission_callback` with `current_user_can()` |

**Nonce verification failure must halt execution immediately** with `wp_die()` or a `WP_REST_Response` error.

### Capability Checks

Every admin page render, settings save, AJAX handler, and REST endpoint **verifies the current user has the required capability via `current_user_can()`**. Use granular capabilities (`edit_posts`, `manage_options`, `manage_woocommerce`) rather than role checks (`is_admin`, `is_editor`). **Role names are mutable and can be redefined by plugins. Capabilities are the canonical authorization mechanism in WordPress.**

**Capability verification executes before any side effect** (database write, file operation, email send, API call). Checking after the action is not a security measure.

### wp-config.php Hardening

`wp-config.php` is the single most sensitive file in a WordPress installation.

| Constant | Required value | Purpose |
|:---------|:--------------:|:--------|
| `DISALLOW_FILE_EDIT` | `true` | Prevents theme/plugin editing from admin dashboard |
| `DISALLOW_FILE_MODS` | `true` | Prevents plugin/theme installation and updates from admin |
| `FORCE_SSL_ADMIN` | `true` | Forces HTTPS on all admin and login pages |
| `WP_DEBUG` | `false` (prod) | Disabled in production; staging/dev only |
| `WP_DEBUG_LOG` | `true` (staging only) | Logs to `wp-content/debug.log` instead of displaying |
| `WP_DEBUG_DISPLAY` | `false` always | Errors in browser expose internal architecture |
| `AUTOMATIC_UPDATER_DISABLED` | `true` | Updates managed through CI/CD, not web interface |
| `WP_POST_REVISIONS` | `5` (or 3-10) | Limits post revision storage |

**Authentication keys and salts** (`AUTH_KEY`, `SECURE_AUTH_KEY`, `LOGGED_IN_KEY`, `NONCE_KEY`, and their `SALT` counterparts) **must be unique, randomly generated 64+ character strings**. Rotate on any suspected compromise. Generate from the WordPress salt API or via CLI tooling during deployment.

**Use a non-default table prefix.** The `wp_` prefix is assumed by automated SQL injection tools. A custom prefix eliminates the lowest-effort attack scripts and reduces automated scan noise.

### XML-RPC and Enumeration Hardening

XML-RPC (`xmlrpc.php`) enables brute-force amplification attacks via the `system.multicall` method and DDoS reflection.

| Target | Mitigation |
|:-------|:-----------|
| **XML-RPC** | Add `xmlrpc_enabled` filter returning `false`. Block `xmlrpc.php` at server config level. Apply Cloudflare WAF rule to drop requests |
| **User enumeration** | Filter `rest_endpoints` to remove `/wp/v2/users` for unauthenticated requests. Block `/?author=N` enumeration via redirect rules or a must-use plugin |
| **Login hardening** | Limit login attempts via plugin or application firewall. Enforce strong passwords. **Require two-factor authentication for all admin-level accounts** |

### Filesystem Permissions

| Path | Permissions |
|:-----|:------------|
| Directories | `755` |
| Files | `644` |
| `wp-config.php` | `440` or `400` |
| `wp-content/uploads/` | Web-server-writable; **no PHP execution** |

**Block PHP execution in uploads via server configuration.** No PHP files in the uploads directory should ever execute.

### Content Security Headers

Set security headers via `wp_headers` filter or server configuration. Apply in a must-use plugin or at the server level for consistency across all responses.

| Header | Value |
|:-------|:------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `SAMEORIGIN` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | Start with `default-src 'self'`; add exceptions for legitimate external resources |

---
[Back to Overview](./OVERVIEW.md)
