# Custom Product Types

WooCommerce ships with six product types: simple, variable, grouped, external/affiliate, and their virtual/downloadable variants. Custom product types extend this set for domain-specific requirements: rentals, subscriptions, bookings, licenses, bundles, composites.

### Registration

**Register custom product types by extending `WC_Product`** (or `WC_Product_Simple` for types that share simple product behavior).

| Step | Required pattern |
|:-----|:-----------------|
| Class name | `WC_Product_{Type}` where `{Type}` matches the `product_type` slug, capitalized and underscore-separated |
| Class registration | In `init` or `plugins_loaded` action |
| Type selector registration | `product_type_selector` filter |
| Class mapping | `woocommerce_product_class` filter |

**Override `get_type()`** in the custom product class to return the product type slug. This slug must be lowercase, alphanumeric with underscores, and match the key used in the `product_type_selector` filter and the `woocommerce_product_class` filter. **Mismatched slugs cause WooCommerce to fall back to `WC_Product_Simple`, losing all custom type behavior.**

### Admin UI

Control which product data tabs display for the custom type using the `product_type_options` filter (for checkboxes like virtual, downloadable) and JavaScript show/hide rules matching WooCommerce's admin JS conventions. Each product type can declare which tabs (General, Inventory, Shipping, Linked Products, Attributes, Advanced) are relevant. **Hide tabs that do not apply** to reduce admin UI complexity.

### Add-to-Cart Templates

Provide a custom add-to-cart template for the product type if the standard simple product add-to-cart button is insufficient. Register the template via `woocommerce_{product_type}_add_to_cart` action. Place the template in `templates/single-product/add-to-cart/{product_type}.php` within the plugin directory. **Use `wc_get_template()`** for template loading so themes can override via the standard WooCommerce template override mechanism.

### Custom Data and Purchasability

- Custom product types that store additional data use `WC_Product::update_meta_data()` and `WC_Product::get_meta()` for HPOS compatibility. Register custom product data fields via `woocommerce_product_options_{tab}` hooks for the classic editor, or via the Gutenberg-based product editor block API. Save in `woocommerce_process_product_meta_{product_type}`.
- **Ensure custom product types are purchasable** by implementing `is_purchasable()`, `add_to_cart_url()`, `add_to_cart_text()`. Without these, the product displays in the catalog but cannot be added to cart. For display-only or request-a-quote types, override `is_purchasable()` to return `false` and provide an alternative CTA.

---
[Back to Overview](./OVERVIEW.md)
