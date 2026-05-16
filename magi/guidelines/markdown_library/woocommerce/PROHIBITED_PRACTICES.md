# Prohibited Practices

### Never Do

- Query `wp_posts`, `wp_postmeta`, or HPOS tables directly for order data. Use `WC_Order` CRUD methods and `wc_get_orders()`.
- Use `WP_Query` with `post_type => 'shop_order'`. Use `WC_Order_Query`.
- Use `get_post_meta` / `update_post_meta` for order data. Use `WC_Order::get_meta` / `update_meta_data`.
- Ship extensions without declaring HPOS compatibility. **Undeclared extensions block HPOS adoption.**
- Use `woocommerce_thankyou` as a fulfillment trigger. Use `woocommerce_payment_complete` or status transition hooks.
- Calculate prices, discounts, or taxes in client-side JavaScript. **All commercial calculations execute server-side through WooCommerce.**
- Process webhook payloads without `X-WC-Webhook-Signature` verification.
- Use the WC REST API (`wc/v3`) for customer-facing cart operations. Use the Store API (`wc/store/v1`).
- Embed WC REST API consumer key/secret in client-side code or mobile apps.
- Store raw credit card numbers, CVVs, or full magnetic stripe data in WooCommerce or its database.
- Serve any WooCommerce page, API endpoint, or webhook over unencrypted HTTP.
- Set `Access-Control-Allow-Origin: *` on WooCommerce API endpoints in production.
- Mix shortcode-based and headless Store API checkout on the same installation without session isolation.
- Use undocumented internal WooCommerce classes or methods that may change without deprecation notice.
- Modify product stock quantities via direct database updates instead of `wc_update_product_stock()`.
- Skip shakedown after a triggering change.
- Mock the payment gateway during shakedown.
- Skip the failure path during shakedown.
- Declare shakedown success without diffing totals against the expected fixture.

---
[Back to Overview](./OVERVIEW.md)
