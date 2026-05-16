# WordPress Development Library

**Runtime:** WordPress 6.4+, PHP 8.1+, MySQL 8.0+ or MariaDB 10.6+.

Defines strict conventions for PHP/WordPress development, plugin authoring, theme integration, REST API hardening, and security posture across WordPress-powered properties. Applies to custom plugins, theme child customizations, WooCommerce extensions, LearnDash integrations, and page builder interoperability (Avada, Elementor).

## Critical Mandates (Read First)

- **WordPress Is Infrastructure, Not a Toy** — Treat every hook, filter, query, and option write with the same rigor applied to any backend service.
- **Hooks Over Hacks** — Never modify core files; never patch vendor plugins directly; never rely on load-order timing not contractually guaranteed.
- **Data Is Sacred** — Every database write passes through the WordPress abstraction layer with proper sanitization, escaping, and prepared statements.
- **Plugin Isolation** — Custom plugins are self-contained; no plugin depends on another being active unless declared, verified at activation, and gracefully degraded.
- **Minimal Admin Surface** — Register only what is required; gate every handler behind capability checks.
- **Golden Rule** — If WordPress provides an API for it, use the API.
- **Shakedown Required** — Mandatory post-deploy integration validation against staging mirroring production after every triggering change.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [PHP Standards and Conventions](./PHP_STANDARDS.md)
3. [Security](./SECURITY.md)
4. [Database Patterns](./DATABASE.md)
5. [REST API](./REST_API.md)
6. [Plugin Architecture](./PLUGIN_ARCHITECTURE.md)
7. [Theme and Page Builder Interoperability](./THEMES_BUILDERS.md)
8. [WooCommerce Patterns](./WOOCOMMERCE.md)
9. [LearnDash Integration](./LEARNDASH.md)
10. [Cron and Background Processing](./CRON.md)
11. [Asset Management](./ASSETS.md)
12. [Multisite Considerations](./MULTISITE.md)
13. [Performance Optimization](./PERFORMANCE.md)
14. [Deployment and Environment Management](./DEPLOYMENT.md)
15. [Shakedown — Integration Validation](./SHAKEDOWN.md)
16. [Internationalization](./I18N.md)
17. [AJAX Patterns](./AJAX.md)
18. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
19. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
20. [Required Practices](./REQUIRED_PRACTICES.md)
21. [Style Summary](./STYLE_SUMMARY.md)
