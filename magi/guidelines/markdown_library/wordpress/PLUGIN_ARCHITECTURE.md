# Plugin Architecture

### Plugin File Structure

The main plugin file handles **bootstrap only**:

- Define constants.
- Load the autoloader.
- Register activation/deactivation/uninstall hooks.
- Instantiate the plugin container or entry class.

Business logic lives in namespaced classes under `src/`. Admin-specific code separates from frontend code. Assets live in `assets/` with a build step for production minification.

### Activation, Deactivation, Uninstall

| Hook | Responsibilities |
|:-----|:-----------------|
| **Activation** | Schema creation, default option seeding, capability registration, rewrite rule flushing |
| **Deactivation** | Cron unscheduling and transient cleanup. **Must not delete user data** |
| **Uninstall** | Full data removal: drop custom tables, delete options, delete transients, remove user meta, remove post meta. **Include a data preservation option for enterprise plugins** managing significant datasets |

### Plugin Dependencies

When a plugin depends on another (WooCommerce, LearnDash):

- **Verify the dependency is active before initializing.** Check in `plugins_loaded` using `function_exists()`, `class_exists()`, or `is_plugin_active()`.
- **Display an admin notice when missing.**
- **Do not fatal error on missing dependencies.**
- For version-specific dependencies, verify the dependency version meets minimum requirements.

### Hook Architecture

WordPress executes hooks in priority order (default 10).

| Priority range | Use |
|:---------------|:----|
| 1-5 | Early setup (post types, taxonomies) |
| 10 | Standard functionality (default) |
| 20-99 | Late-stage modifications |

**Document priority choices when deviating from default.** Use named functions or class methods as callbacks so hooks can be removed by other code.

**Hooks registered with anonymous closures cannot be removed.** For extensibility, use named callbacks. The only exception is must-use plugins that intentionally prevent removal of security-critical filters.

### Must-Use Plugins

Must-use plugins (`mu-plugins/`):

- Load **before regular plugins**.
- **Cannot be deactivated**.
- Execute in alphabetical filename order.
- Use for security hardening, environment detection, performance optimizations, shared utility functions.
- **Have no activation/deactivation hooks.** Keep minimal.

### Settings API Usage

Use the WordPress Settings API (`register_setting`, `add_settings_section`, `add_settings_field`) for plugin configuration pages. The Settings API provides nonce verification, capability checking, and sanitization callbacks automatically when used correctly. **Register settings with a `sanitize_callback` that validates every field.** Use the options API (`get_option`/`update_option`) for storage. **Group related settings into a single serialized option array** to reduce option table rows and autoload overhead.

---
[Back to Overview](./OVERVIEW.md)
