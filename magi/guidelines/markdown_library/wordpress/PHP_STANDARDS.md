# PHP Standards and Conventions

### PHP Version Baseline

All new code targets **PHP 8.1+ minimum**. Use typed properties, union types, enums, readonly properties, named arguments, and match expressions where they improve clarity. Do not use features from PHP versions beyond what the production host supports. **Verify host PHP version in plugin activation hooks.**

### Type Discipline

**Every PHP file begins with `declare(strict_types=1);` immediately after the opening tag.**

Type all function parameters, return values, and class properties. Use union types for values that legitimately vary. **Never use `mixed` as a type declaration unless interfacing with WordPress core functions** that genuinely return unpredictable types — and in those cases, cast or validate immediately after the call.

### Naming Conventions

Follow WordPress PHP Coding Standards for contributions to themes and public-facing code. For custom plugin internals, **PSR-12 autoloaded namespaces are acceptable and preferred** for complex plugin architectures.

**Prefix all global functions, constants, hooks, option names, transient keys, and post meta keys with the plugin slug** to prevent namespace collisions. A plugin named `acme-analytics` prefixes everything with `acme_analytics_` or uses the `AcmeAnalytics` namespace.

| Identifier | Pattern |
|:-----------|:--------|
| Custom hooks | `{plugin_slug}/{action_description}` (actions); `{plugin_slug}/{filter_description}` (filters) |
| Option keys | `{plugin_slug}_{setting_name}`; **never exceed 191 characters** (options table key limit) |
| Transient keys | `{plugin_slug}_{cache_identifier}`; **never exceed 172 characters** (WP adds `_transient_` prefix; combined must stay under 191) |
| Post meta keys | `_{plugin_slug}_{field_name}` with leading underscore to hide from Custom Fields UI when programmatic-only |

### Autoloading

Use **Composer autoloading (PSR-4)** for custom plugin class hierarchies. Ship `vendor/autoload.php` with the plugin. Do not rely on WordPress users having Composer installed. For plugins distributed via the WordPress.org repository, bundle the autoloader. For private plugins deployed via CI/CD, generate the optimized classmap autoloader during build.

### Error Handling in PHP Context

WordPress suppresses errors by default in production via `WP_DEBUG=false`. **Custom code must not rely on this suppression.**

- Use try-catch for operations that can throw.
- **Return `WP_Error` objects** from functions that can fail rather than returning `false` or `null`.
- **Check `is_wp_error()`** on every function call that documents `WP_Error` as a possible return.
- Log errors via `error_log()` or a structured logging plugin.
- **Never echo errors to the frontend in production.**

---
[Back to Overview](./OVERVIEW.md)
