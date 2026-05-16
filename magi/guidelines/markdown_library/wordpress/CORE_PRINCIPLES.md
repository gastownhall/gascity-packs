# Core Principles

### WordPress Is Infrastructure, Not a Toy

WordPress runs production revenue paths. **Treat every hook, filter, query, and option write with the same rigor applied to any backend service.** Sloppy WordPress code is sloppy production code.

### Hooks Over Hacks

WordPress exposes an extensive action and filter system. **Use it.** Never modify core files. Never patch vendor plugins directly. Never rely on load-order timing that is not contractually guaranteed by the hook API. **If a hook does not exist for the behavior you need, create one in your own plugin and petition upstream for inclusion.**

### Data Is Sacred

Every database write passes through the WordPress abstraction layer with proper sanitization, escaping, and prepared statements. **Direct SQL writes bypassing `wpdb` are prohibited** except in migration scripts with explicit justification. Every read that renders to a browser escapes on output.

### Plugin Isolation

Custom plugins are self-contained units. **No plugin depends on another plugin being active unless that dependency is declared, verified at activation, and gracefully degraded when absent.** Shared logic lives in a dedicated utilities plugin or a must-use plugin — never duplicated across plugin boundaries.

### Minimal Admin Surface

Every admin page, AJAX endpoint, REST route, and settings field is a potential attack vector. **Register only what is required.** Gate every handler behind capability checks. **Remove default WordPress features that are unused in production** (XML-RPC, application passwords, REST user enumeration) unless explicitly needed.

### Golden Rule

**If WordPress provides an API for it, use the API.** If it does not, build a clean abstraction that can be replaced when it does. This includes:

- Database queries (`WP_Query` / `wpdb`).
- HTTP requests (`wp_remote_get` / `wp_remote_post`).
- Filesystem operations (`WP_Filesystem`).
- Cron (`wp_schedule_event`).

---
[Back to Overview](./OVERVIEW.md)
