# Prohibited Practices

### Never Do

- Modify WordPress core files. **Core updates overwrite changes.** Use hooks, filters, and drop-ins.
- Access `$_GET` / `$_POST` / `$_REQUEST` / `$_COOKIE` / `$_SERVER` without sanitization.
- Concatenate variables into SQL queries. **Use `$wpdb->prepare()` for every parameterized query.**
- Process form submissions or AJAX without nonce verification.
- Execute privileged operations without `current_user_can()`. **Missing checks enable privilege escalation.**
- Use `is_admin()` as a security check. **It checks context, not capability.** AJAX requests return `true` regardless of user role.
- Output dynamic values without `esc_html()` / `esc_attr()` / `esc_url()` / `wp_kses()`. **XSS results from unescaped output.**
- Hardcode `wp_` in queries. **Use `$wpdb->prefix`** for multisite and custom-prefix compatibility.
- Use `posts_per_page => -1` in frontend loads. **Unbounded queries crash sites with large datasets.**
- Ship plugins without uninstall cleanup. **Removed plugins must remove all database artifacts.**
- Enqueue assets outside `wp_enqueue_scripts` / `admin_enqueue_scripts`. Causes dependency and duplication failures.
- Use raw PHP file functions instead of `WP_Filesystem`. Bypasses deployment abstraction.
- Store API keys or tokens in the options table unencrypted. **Use environment variables or secrets managers.**
- Register critical hooks with anonymous closures. **Prevents removal by child themes and other plugins.**
- Set `DISABLE_WP_CRON` without system cron replacement. **Scheduled events stop entirely.**
- Skip shakedown after a triggering change.
- Run shakedown without `WP_DEBUG` enabled.
- Optimize during shakedown.

---
[Back to Overview](./OVERVIEW.md)
