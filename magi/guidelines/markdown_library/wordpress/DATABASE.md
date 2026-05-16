# Database Patterns

### wpdb Usage

All database interactions use the global `$wpdb` object. **Direct PDO or mysqli connections are prohibited in plugin and theme code.** The `wpdb` layer provides prepared statements, table prefix awareness, and error handling integration.

- **Every query containing user-supplied or variable data uses `$wpdb->prepare()` with typed placeholders.** No exceptions. **String concatenation into SQL is a SQL injection vulnerability regardless of prior sanitization.**
- **Reference tables via `$wpdb->prefix` or built-in properties** (`$wpdb->posts`, `$wpdb->options`). **Hardcoding `wp_` breaks multisite and custom-prefix installations.**

### WP_Query and get_posts

Use `WP_Query` for complex post retrieval. Use `get_posts()` for simple, non-paginated lists. Both respect WordPress caching layers and access controls. **Never use direct SELECT queries against the posts table for standard content retrieval.** Direct queries are reserved for aggregate operations, reporting, or migrations where the full post object is unnecessary.

| Constraint | Pattern |
|:-----------|:--------|
| Pagination not needed | `no_found_rows => true` — eliminates `SQL_CALC_FOUND_ROWS` overhead |
| IDs only | `fields => 'ids'` — returns integer array instead of full `WP_Post` objects |
| `posts_per_page` | Limit to minimum required. **Never `-1` in production page loads.** Use `-1` only in admin contexts, background jobs, or CLI commands |
| Meta queries | Minimize in frontend queries. JOINs against `postmeta` lack indexes. **For frequently filtered meta, use a custom taxonomy or a dedicated lookup table** |

### Custom Database Tables

Custom tables are justified when the EAV schema (`postmeta`, `usermeta`, `termmeta`, `options`) creates performance problems or when data does not fit the post/term/user model.

- Use `dbDelta()` for table creation and schema updates.
- Register table creation in the plugin **activation hook**.
- Register cleanup in the **uninstall hook**, not the deactivation hook.
- **`dbDelta()` has strict formatting requirements**: two spaces after `PRIMARY KEY`, column definitions on separate lines, `KEY` keyword for indexes.

### Transient API

Transients are the WordPress-native caching mechanism for expensive computed values, external API responses, and aggregated data.

| Constraint | Required |
|:-----------|:---------|
| Expiration | **Always set an expiration.** Transients without expiration bypass the object cache and live permanently in the options table |
| Key length | **Must not exceed 172 characters**. WP prefixes with `_transient_` (11) and `_transient_timeout_` (19); options key column is 191 |
| Serialization | Automatic. Store arrays and objects directly. Do not pre-serialize unless JSON is needed for external consumption |
| Race conditions | Transient regeneration after expiry can cause cache stampedes under load. **Implement a lock-and-regenerate pattern or use soft expiration** for high-traffic transients |
| Invalidation | **Delete transients explicitly when underlying data changes.** Do not rely solely on TTL. Use `delete_transient()` in `save_post`, `updated_option`, or relevant domain hooks |

### Object Cache

WordPress object cache (`wp_cache_get`, `wp_cache_set`) provides per-request caching by default. **With a persistent drop-in (Redis, Memcached), it becomes cross-request.** Design code to function correctly with and without a persistent cache. Use cache groups to namespace per plugin. Implement `wp_cache_flush_group()` (WordPress 6.1+) for targeted invalidation instead of full flushes.

---
[Back to Overview](./OVERVIEW.md)
