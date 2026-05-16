# Deployment and Environment Management

### Environment Separation

Maintain local, staging, and production environments. **Use `wp_get_environment_type()` to detect context.** Set via `WP_ENVIRONMENT_TYPE` constant or environment variable. Enable debug features by environment type only. **Never enable `WP_DEBUG`, `SCRIPT_DEBUG`, or `SAVEQUERIES` in production.**

### Version Control Strategy

Track in version control:

- Custom plugins.
- Child themes.
- mu-plugins.
- `wp-config.php` (with secrets externalized).

Manage WordPress core and third-party dependencies via Composer or deployment scripts pulling specific versions. **Uploads are never version-controlled.** Gitignore excludes `wp-content/uploads`, `vendor/`, `node_modules/`, and generated assets.

### Database Migrations

- Track schema versions in a plugin-specific option.
- On load, compare stored version against code version.
- Run sequential, idempotent migration functions on mismatch.
- Use `dbDelta()` for schema changes and prepared statements for data.
- **Log migration execution.**
- **Roll forward only.** Halt and alert on failure rather than partially applying changes.

### Deployment Pipeline

Deployments run through a CI/CD pipeline:

1. Lint PHP (PHPCS with WordPress standards).
2. Run unit tests (PHPUnit with `WP_UnitTestCase`).
3. Build production assets (minified CSS/JS).
4. Deploy to staging.
5. Run smoke tests.
6. Promote to production.

**Post-deployment steps:**

- Flush rewrite rules (`flush_rewrite_rules()` via WP-CLI).
- Clear object cache.
- Clear page cache.
- Clear page builder caches.

**Never deploy directly to production via FTP, the WordPress admin, or manual file copy.**

---
[Back to Overview](./OVERVIEW.md)
