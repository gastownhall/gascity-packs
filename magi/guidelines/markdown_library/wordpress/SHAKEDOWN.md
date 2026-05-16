# Shakedown — Integration Validation

A WordPress shakedown is a **mandatory post-deploy integration-validation pass that exercises every critical wiring point of the platform end-to-end under real but controlled conditions**. It answers one question: **does this WordPress installation actually work when every hook, filter, cron event, REST route, database connection, object cache, and permalink rewrite fires together against the real production PHP runtime and database?** It is not a PHPUnit suite, not a Query Monitor profiling session, and not a security scan — it is the **first controlled execution of the full integrated stack** after a change that touches integration boundaries.

### Definition

A shakedown is the first controlled, end-to-end execution of a WordPress installation under real operating conditions on the target PHP version, against the target database, with the target object cache and web server configuration. It validates that:

- `wp-admin` renders without a white screen of death.
- All active plugins boot without fatal errors.
- The theme renders critical templates.
- `wp-cron` fires.
- The REST API responds with the expected shape.
- Every subsystem the site depends on (database, object cache, mail, storage, external APIs) is reachable and functional from inside the WordPress process.

### Preflight vs Shakedown vs Testing

| Phase | What it validates |
|:------|:------------------|
| **Preflight** | The WP-CLI doctor layer: `wp doctor check --all`, `wp core verify-checksums`, `wp plugin status`, `wp theme status`, PHP version, required `wp-config.php` constants, filesystem permissions, disk space. **Answers: "is the environment ready to run WordPress at all"** |
| **Shakedown** | Plugins activate cleanly, admin loads, front-end renders, `wp-cron` dispatches, REST API returns, database round-trips, object cache connects. **Answers: "is the integrated stack actually executing"** |
| **Testing** | PHPUnit, Query Monitor, Cypress/Playwright, accessibility, Core Web Vitals. **Answers: "is the site correct and performant"** |

A site that passes preflight is **installable**. A site that passes shakedown is **integrated**. A site that passes testing is **correct and performant**.

### Mandatory Triggers

A WordPress shakedown is mandatory after:

- WordPress core update (minor or major), including automatic background updates.
- **Plugin activation, deactivation, update, or replacement** — even a single plugin, even a "minor" patch.
- Theme update, theme switch, or parent theme change.
- Child theme `functions.php` changes that touch hooks, filters, or enqueues.
- PHP version change or PHP extension install/removal.
- Database migration, server move, or switch between MySQL and MariaDB.
- Web server change or rewrite rule reconfiguration.
- Object cache change (enabling/disabling Redis or Memcached, changing the drop-in).
- Multisite network-activation, site-creation, or domain-mapping change.
- `wp-config.php` constant change affecting runtime behavior (`WP_CACHE`, `DISALLOW_FILE_MODS`, `WP_ENVIRONMENT_TYPE`, table prefix).
- Restore from backup, migration from another host, or clone of production into staging.
- Extended dormancy on staging or maintenance environments that may have drifted from production.

### Non-Triggers

- Post, page, or media content edits through the admin that do not touch code, configuration, or plugin state.
- Menu item reordering, widget placement, or visual customization through the Customizer.
- User account creation, role assignment, or password resets.
- Setting changes within validated admin panels that do not touch `wp-config.php` or plugin activation state.
- Revision cleanup, transient purging, or other routine housekeeping via WP-CLI.

### Validation Categories

| Category | What is verified |
|:---------|:-----------------|
| **Data flow integrity** | Front-end request bootstraps WordPress, runs `WP_Query`, executes template hierarchy, runs `the_content` filters, returns rendered HTML. Admin requests route through `wp-admin` and render expected widgets. REST GET `/wp-json/wp/v2/posts` returns well-formed JSON |
| **Subsystem communication** | `$wpdb` connection establishes and executes a sample SELECT. Persistent object cache (Redis/Memcached) connects via the drop-in and round-trips a test key. `wp_mail` delivers a test message through the configured provider. `WP_Filesystem` initializes and reads `wp-content/uploads`. `wp_remote_get` reaches external targets |
| **Resource availability** | PHP memory during full front-end and admin renders stays within `WP_MEMORY_LIMIT` and `WP_MAX_MEMORY_LIMIT`. Open file handles, DB connections, cache connections released at end of request. **No PHP fatals, no memory exhaustion, no MySQL gone-away, no zombie processes** |
| **Configuration propagation** | `wp-config.php` constants (`WP_DEBUG`, `WP_ENVIRONMENT_TYPE`, `DISABLE_WP_CRON`, `DISALLOW_FILE_EDIT`, `DISALLOW_FILE_MODS`, `FORCE_SSL_ADMIN`, table prefix, salts) read by bootstrap and propagated. Plugin settings load through `get_option()`. Environment-specific overrides activate based on `wp_get_environment_type()`. Secrets present and usable |
| **Error handling paths** | `WP_DEBUG_LOG` captures notices and warnings with full stack context. `WP_Error` objects propagate without being swallowed. Plugin activation failures roll back cleanly. **Fatal errors trigger recovery mode email and site-health notice rather than a blank white screen** |
| **Side effect correctness** | Test post save fires `save_post`, `transition_post_status`, related hooks **exactly once**. Scheduled `wp-cron` event runs its callback on schedule. Media upload writes exactly one file at expected `YYYY/MM` path with intermediate sizes generated. Plugin activation runs `dbDelta` migration once and records schema version |

### Execution Principles

- **Conservative** — Exercise the happy path with a known-good test post, test user, test media file. Do not test edge cases, do not stress the REST API, do not run load tests.
- **Progressive stress** — Begin with `wp-admin` login and dashboard. Then home page. Then single post, archive, 404. Then REST API. Then `wp-cron`. **Add complexity one step at a time and stop at the first failure.**
- **Controlled environment** — Staging mirrors production: same PHP version, database engine and version, object cache, web server, plugin set, theme. Sanitize production data for PII but **preserve schema and volume characteristics**.
- **Observable execution** — Enable `WP_DEBUG`, `WP_DEBUG_LOG`, and `SAVEQUERIES` for the shakedown session. Tail `wp-content/debug.log`, web server error log, PHP error log simultaneously. **Capture every notice, warning, and deprecation.**
- **Known-good inputs** — Curated shakedown fixture: specific post ID, page ID, user account, media file. Expected output recorded and compared.
- **No optimization during shakedown** — Log slow queries, heavy pages, large transients, but **do not tune anything during the pass**. Optimization is a testing concern.

### Execution Pattern

1. **Confirm preflight passed**: `wp doctor check --all` returns success, `wp core verify-checksums` returns clean, `wp plugin status` shows expected active set, required constants present.
2. **Initialize controlled environment**: enable `WP_DEBUG` and `WP_DEBUG_LOG`, truncate `wp-content/debug.log`, clear object cache via `wp cache flush`, clear page cache, flush rewrite rules.
3. **Execute admin path**: log in, load dashboard, verify no fatal errors in `debug.log`, no PHP errors in web server log, plugin list shows no activation errors.
4. **Execute front-end path**: home page, single post, category archive, guaranteed-404 URL. Verify HTTP 200/404 and non-empty rendered HTML.
5. **Execute REST API path**: GET `/wp-json/`, GET `/wp-json/wp/v2/posts`, GET `/wp-json/wp/v2/posts/{id}`. Verify JSON shape, status codes, response headers.
6. **Execute cron path**: `wp cron event run --due-now`, verify every due event ran and returned success, verify scheduled events remain in `wp_options` cron array.
7. **Execute side-effect path**: `wp post create` with test content, verify `save_post` hooks fire, `wp media import` test image, verify file lands in `wp-content/uploads` with intermediate sizes, `wp post delete` fixture, verify cleanup.
8. **Execute object cache path**: `wp cache set` and `wp cache get` test key, verify round-trip, verify cache backend shows the key through its native CLI.
9. **Record observations** — `debug.log` contents, web server error log entries, query count from `SAVEQUERIES`, anomalies. Classify the pass.

### Reference Shakedown Sequence (WP-CLI)

```bash
# ─── Preflight confirmation ───
wp doctor check --all
wp core verify-checksums
wp plugin status
wp theme status

# ─── Initialize controlled environment ───
wp config set WP_DEBUG true --raw --type=constant
wp config set WP_DEBUG_LOG true --raw --type=constant
wp config set SAVEQUERIES true --raw --type=constant
: > wp-content/debug.log
wp cache flush
wp rewrite flush --hard

# ─── Admin path ───
wp eval 'wp_set_current_user( get_user_by( "login", "shakedown_admin" )->ID ); require_once ABSPATH . "wp-admin/admin.php";'
grep -E "PHP (Fatal|Parse|Warning|Notice)" wp-content/debug.log && exit 1

# ─── Front-end path ───
wp eval '$r = wp_remote_get( home_url( "/" ) ); if ( is_wp_error( $r ) || 200 !== wp_remote_retrieve_response_code( $r ) ) { exit( 1 ); }'
wp eval '$r = wp_remote_get( home_url( "/?p=" . (int) get_option( "shakedown_test_post_id" ) ) ); if ( is_wp_error( $r ) || 200 !== wp_remote_retrieve_response_code( $r ) ) { exit( 1 ); }'
wp eval '$r = wp_remote_get( home_url( "/this-url-must-404-xyz" ) ); if ( 404 !== wp_remote_retrieve_response_code( $r ) ) { exit( 1 ); }'

# ─── REST API path ───
wp eval '$r = wp_remote_get( rest_url( "wp/v2/posts" ) ); $body = json_decode( wp_remote_retrieve_body( $r ), true ); if ( ! is_array( $body ) || empty( $body ) ) { exit( 1 ); }'

# ─── wp-cron path ───
wp cron event run --due-now

# ─── Side-effect path ───
POST_ID=$(wp post create --post_title="Shakedown Fixture" --post_status=publish --porcelain)
wp media import /path/to/shakedown-fixture.jpg --post_id="${POST_ID}"
wp post delete "${POST_ID}" --force

# ─── Object cache path ───
wp cache set shakedown_canary "ok" default 60
wp eval 'if ( "ok" !== wp_cache_get( "shakedown_canary", "default" ) ) { exit( 1 ); }'

# ─── Final artifact capture ───
wp cli info > shakedown_env.txt
wp plugin list --format=json > shakedown_plugins.json
cp wp-content/debug.log shakedown_debug.log

# ─── Classify pass ───
if [[ -s wp-content/debug.log ]]; then
    echo "Shakedown FAIL-BLOCKING: debug.log is non-empty"
    exit 1
fi
echo "Shakedown PASS"
```

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| **Pass** | Every validation step executed cleanly. `wp-admin` loaded, front-end rendered, REST API responded, `wp-cron` dispatched, media round-tripped, `debug.log` is clean. **Cleared for promotion** |
| **Fail-blocking** | White screen on admin, fatal in plugin activation, 500 from REST API, `wp-cron` event throws, database connection failure. **Fix root cause and re-run from step 1** |
| **Fail-nonblocking** | PHP deprecation notice, slow query, transient expiration that did not refresh. **Log the issue with full context and proceed with caution** |
| **Inconclusive** | Staging object cache unavailable, SMTP rate-limited test send. **Adjust environment and re-run the specific validation** |

### Required Artifacts

- **Execution log** — Full timestamped log of WP-CLI commands run, stdout/stderr, contents of `wp-content/debug.log`, web server access and error logs for the shakedown window.
- **Result summary** — Pass/fail classification per validation category (data flow, subsystem communication, resource availability, configuration propagation, error handling, side effects) with the specific step that produced the classification.
- **Issue list** — Every anomaly observed, classified blocking/non-blocking/deferred, with reproduction steps and originating log excerpt.
- **Environment snapshot** — WordPress version, PHP version, database engine and version, object cache backend and version, active plugin list with versions, active theme with version, `wp-config.php` constant values (with secrets redacted), web server and version. **Establishes the validated baseline.**

### Anti-Patterns

- **Skipping shakedown after a "small" plugin update.** Plugin updates touch activation code, `dbDelta` migrations, option defaults, and hook registrations — every one is an integration boundary.
- **Treating shakedown as a PHPUnit replacement.** Shakedown exercises the integrated runtime with a handful of representative inputs. PHPUnit exercises isolated units. **Different problems.**
- **Running shakedown on a stripped staging environment** that differs from production in PHP version, plugin set, theme, or database engine. Non-representative environment produces non-representative results.
- **Optimizing during shakedown.** Noticing a slow query and rewriting it during the pass introduces a new change that itself requires a shakedown. **Log the observation and move on.**
- **Running shakedown without `WP_DEBUG` enabled.** Without `debug.log` capture, every silent notice and warning passes unnoticed and **the pass is fabricated**.
- **No recorded artifacts.** A green checkmark in someone's head is not a shakedown record.

---
[Back to Overview](./OVERVIEW.md)
