# Payment Gateway Integration

Payment gateways bridge WooCommerce checkout with payment processors. WooCommerce abstracts the gateway interface via `WC_Payment_Gateway`, providing a standardized integration point for any payment processor.

### Gateway Class Structure

**Custom payment gateways extend `WC_Payment_Gateway`** and register via the `woocommerce_payment_gateways` filter. The gateway class implements `process_payment($order_id)`, which receives the order, communicates with the payment processor, and returns a result array indicating success (with redirect URL) or failure (with error message). **Never process payments outside the gateway class** — this bypasses WooCommerce's payment error handling, logging, and retry infrastructure.

### Redirect-Based Flows

For redirect-based payment flows (PayPal, Stripe Checkout, bank transfers):

1. Set the order status to `pending` in `process_payment()`.
2. Redirect the customer to the processor.
3. Confirm payment completion via a webhook or callback URL.

**Do not mark the order as `processing` or `completed` in `process_payment()` before the payment processor confirms success.** The callback handler (typically a custom REST endpoint or admin-ajax handler) verifies the payment, updates the order status, and triggers fulfillment.

### Credentials

Store payment gateway credentials (API keys, merchant IDs, webhook secrets) in the gateway's settings (WooCommerce > Settings > Payments > {Gateway}), **not in `wp-config.php` or environment variables for this specific use case** — WooCommerce's settings API encrypts sensitive fields and integrates with the admin UI. For environments requiring externalized secrets (containerized deployments, CI/CD-managed configs), override the gateway settings with environment variables via a plugin that maps env vars to WooCommerce options at runtime.

### Refunds

Implement `process_refund($order_id, $amount, $reason)` for gateways that support programmatic refunds. This enables WooCommerce admin refund processing to route through the payment processor automatically. Return `true` on success, `WP_Error` on failure. **Log refund transaction IDs in order notes for audit trail.**

### Block Checkout / Headless Compatibility

Declare support for the Store API checkout flow via `__experimentalRegisterCheckoutData` or the `woocommerce_blocks_payment_method_type_registration` action. **The block-based checkout (and headless checkout via Store API) requires gateways to register their payment method type with the Checkout Blocks system.** Gateways that only support the legacy shortcode checkout do not appear in the block-based or headless checkout flow.

---
[Back to Overview](./OVERVIEW.md)
