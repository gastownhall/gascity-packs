# WooCommerce Patterns

### Integration Architecture

WooCommerce extends WordPress with custom post types (`product`, `shop_order`, `shop_coupon`), taxonomies (`product_cat`, `product_tag`, `product_type`), and a comprehensive hook system.

**WooCommerce 8.x+ High-Performance Order Storage (HPOS)** moves orders to dedicated custom tables. **Declare HPOS compatibility via `before_woocommerce_init`** using `FeaturesUtil::declare_compatibility()`. **Plugins querying orders via `WP_Query` against `shop_order` break under HPOS.** Use `wc_get_orders()` and `WC_Order_Query` for all order retrieval.

### WooCommerce Hook Patterns

WooCommerce exposes hundreds of hooks across storefront, cart, checkout, order processing, and admin. **Use the most specific hook available.** For checkout field customization, use `woocommerce_checkout_fields` filter rather than DOM manipulation. For order status changes, hook into `woocommerce_order_status_{status}` for status-specific logic or `woocommerce_order_status_changed` for cross-status handling.

### WooCommerce REST API

WooCommerce provides its own REST API under `wc/v3`. **Authenticate with consumer key/secret pairs over HTTPS exclusively.** For frontend JavaScript, use the **Store API endpoints (`wc/store/v1`)** designed for headless consumption that handle cart and checkout flows without consumer key authentication. Server-to-server integrations use basic auth with consumer credentials.

### WooCommerce Webhooks

Webhooks notify external systems of events. Configure via admin or REST API. **Webhooks include an `X-WC-Webhook-Signature` header computed with HMAC-SHA256.** **Always verify this signature before processing payloads** on the receiving end. Delivery retries use exponential backoff and auto-disable after repeated failures. Monitor delivery status and implement dead-letter handling on the consumer side.

### Cart and Session Handling

WooCommerce manages cart state via `WC_Session_Handler`, stored in custom tables or object cache. **For headless frontends consuming the Store API, cart state uses the `Cart-Token` header.** **Do not mix shortcode-based checkout with headless flows on the same installation without session isolation.** Persistent carts for logged-in users rely on user meta — ensure it is not purged by cleanup plugins.

### WooCommerce Extension Patterns

| Extension point | Mechanism |
|:----------------|:----------|
| Custom product types | Extend `WC_Product`; register via `woocommerce_product_class` filter |
| Custom order statuses | Register via `register_post_status()` and `wc_order_statuses` filter |
| Payment gateway integrations | Extend `WC_Payment_Gateway`; register via `woocommerce_payment_gateways` filter |
| Shipping method integrations | Extend `WC_Shipping_Method`; register via `woocommerce_shipping_methods` |

**Each extension point has specific lifecycle hooks for initialization, validation, and processing. Follow the extension's documented interface — do not monkey-patch internal WooCommerce methods.**

---
[Back to Overview](./OVERVIEW.md)
