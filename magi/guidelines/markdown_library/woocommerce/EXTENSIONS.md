# Extension Development Patterns

WooCommerce extensions follow WordPress plugin patterns plus WooCommerce-specific conventions for compatibility, data access, and lifecycle management.

### Compatibility Declarations

**Declare WooCommerce version compatibility in the plugin header**:

```text
WC requires at least: 9.0
WC tested up to: 9.6
```

Declare HPOS compatibility, block checkout compatibility, and any feature compatibility via the `before_woocommerce_init` hook using `Automattic\WooCommerce\Utilities\FeaturesUtil::declare_compatibility()`. **Missing compatibility declarations trigger admin warnings and may cause WooCommerce to disable features.**

### WooCommerce Active Check

**Verify WooCommerce is active before initializing extension logic.** Check in the `plugins_loaded` action using `class_exists('WooCommerce')` or `function_exists('WC')`. Display an admin notice and return early if WooCommerce is not active. **Fatal errors from calling WooCommerce functions when WooCommerce is deactivated crash the entire WordPress admin.**

### Public API Only

**Never use internal WooCommerce classes, methods, or functions that are not part of the documented public API.** Internal methods (prefixed with underscore or residing in internal namespaces) change without deprecation notice between WooCommerce versions. **Use the CRUD layer, hook system, and documented utility functions exclusively.**

### Logging

Use the WooCommerce logging system (`wc_get_logger()`) for extension logging rather than `error_log()` or custom logging. The WC logger integrates with WooCommerce's Status > Logs page, supports log sources for filtering, and respects the configured log handler. **Provide a log source identifier matching the extension slug** for easy filtering.

### Marketplace Testing

Integrate the **Quality Insights Toolkit (QIT)** into the development workflow for extensions distributed via the WooCommerce Marketplace. QIT tests extensions against new PHP, WooCommerce, and WordPress releases, as well as against other active extensions, **catching compatibility issues before release**.

---
[Back to Overview](./OVERVIEW.md)
