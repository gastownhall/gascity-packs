# Required Practices

### Always Do

- Begin every PHP file with `declare(strict_types=1);`.
- Sanitize every external input with the most restrictive appropriate function.
- Escape every dynamic value at the point of output matching the context.
- **Verify nonces** on every state-changing request.
- **Verify user capabilities** before every privileged operation.
- Use `$wpdb->prepare()` with typed placeholders for every variable query.
- Prefix all global identifiers with the plugin slug.
- Provide uninstall cleanup that removes all plugin data.
- **Declare HPOS compatibility** in WooCommerce-adjacent plugins. Use `wc_get_orders()`.
- Register and enqueue all assets through the WordPress API within correct hooks.
- Load assets only on pages requiring them.
- Always provide expiration on transients.
- Develop with `WP_DEBUG` and `WP_DEBUG_LOG` enabled. **Fix all notices before merge.**
- Track schema versions and run idempotent migrations on mismatch.
- Unschedule all custom cron events in deactivation hooks.
- Run shakedown after every triggering change against staging that mirrors production.
- Capture all required shakedown artifacts (execution log, result summary, issue list, environment snapshot).

---
[Back to Overview](./OVERVIEW.md)
