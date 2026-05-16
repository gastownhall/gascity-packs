# Order Lifecycle and State Management

### Standard Status Flow

```text
pending → processing → completed
       ↘ failed | cancelled | refunded (any point)
```

| Status | Meaning |
|:-------|:--------|
| `pending` | Created, awaiting payment |
| `processing` | Payment received, awaiting fulfillment |
| `completed` | Fulfilled and delivered |
| `failed` / `cancelled` / `refunded` | Terminal states |

Custom logic that skips statuses (`pending → completed` without `processing`) **must be explicitly justified and documented**. Each status transition fires `woocommerce_order_status_{old}_to_{new}` and `woocommerce_order_status_changed` hooks that downstream systems depend on.

### Status Transitions

**Transition order status via `$order->set_status()` + `$order->save()`, or `$order->update_status()`.** Never update status by modifying the database directly. The status transition methods fire hooks, trigger email notifications, record status change notes, and update related metadata. **Direct database updates bypass all of these.**

### Fulfillment Trigger

**Do not use `woocommerce_thankyou` as a fulfillment trigger.** The thank-you page fires on the client redirect after checkout, which is unreliable: the customer may close the browser, the redirect may fail, or the page may be revisited. **Use `woocommerce_payment_complete` or `woocommerce_order_status_processing`** as the trigger for post-payment fulfillment logic. These fire server-side when the payment gateway confirms success.

### Custom Order Statuses

Register custom order statuses via `register_post_status()` (for backward compatibility) and the `wc_order_statuses` filter. Custom statuses define a label, public visibility setting, and whether they appear in admin reports. Common custom statuses: `wc-awaiting-shipment`, `wc-in-production`, `wc-quality-check`. **Prefix custom status slugs with `wc-`** for WooCommerce compatibility. Custom statuses that bypass `processing` must still trigger fulfillment-related hooks.

### Order Notes

Add order notes (`$order->add_order_note()`) for every significant automated action: payment captured, inventory reserved, shipment dispatched, refund initiated, access granted. Order notes create an auditable timeline visible to store admins and (optionally) customers. **Automated notes include the system/service that performed the action and relevant identifiers** (transaction ID, tracking number, API request ID).

### Order Concurrency and Locking

Orders may be modified concurrently by webhooks, admin actions, cron jobs, and API calls. Without concurrency control, race conditions cause lost updates, duplicate fulfillments, and inconsistent state.

- **Implement idempotency guards** in webhook handlers and automated order processors. Check the order's current status before applying a transition. If the order is already in the target status (e.g., already `completed` when the fulfillment webhook fires), skip processing and log the duplicate. Use order meta flags (e.g., `_fulfillment_processed = true`) with atomic check-and-set patterns to prevent double-processing.
- **For high-concurrency operations** (flash sales, bulk order processing), use database transactions or WooCommerce's built-in order locking where available. The HPOS storage backend supports row-level locking on the `wp_wc_orders` table — more granular than the post-level locking in legacy storage.

---
[Back to Overview](./OVERVIEW.md)
