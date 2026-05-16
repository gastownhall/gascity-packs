# Subscription and Recurring Billing

WooCommerce Subscriptions extends WooCommerce with recurring billing, subscription lifecycle management, and automated renewal processing. Subscriptions introduce the `shop_subscription` post type (HPOS-compatible in current versions) and additional order statuses for recurring payment events.

### Subscriptions API

**Use WooCommerce Subscriptions API functions for subscription operations**: `wcs_get_subscription()`, `wcs_get_subscriptions()`, `WC_Subscription` CRUD methods. **Do not manipulate subscription data directly.** Subscriptions have their own lifecycle hooks (`woocommerce_subscription_status_changed`, `woocommerce_subscription_renewal_payment_complete`) that must fire for downstream systems to react correctly.

### Renewal Failures

Handle renewal payment failures via the `woocommerce_subscription_renewal_payment_failed` hook. Configure the retry schedule in WooCommerce > Settings > Subscriptions > Failed Payments. **Implement customer notifications with a payment update link** (Customer Portal or custom SetupIntent page) to capture a new payment method. **Do not automatically cancel subscriptions on first renewal failure** — configure multiple retry attempts with increasing intervals.

### Lifecycle Testing

**Test subscription lifecycle flows in staging** (trial → active → renewal → failed payment → retry → cancellation) using test payment gateway credentials. Subscription flows involve time-dependent state transitions that are difficult to test manually. Use WP-CLI or custom scripts to advance subscription dates for testing. WooCommerce Subscriptions provides debug tools for simulating renewals.

---
[Back to Overview](./OVERVIEW.md)
