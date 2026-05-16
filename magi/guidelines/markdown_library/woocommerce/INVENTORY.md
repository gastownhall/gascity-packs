# Inventory and Stock Management

WooCommerce tracks stock at the product and variation level. **Stock management governs availability display, overselling prevention, backorder policy, and low-stock notifications.**

### Stock Updates

**Enable Manage stock at the product level** for any product with finite inventory. WooCommerce decrements stock on order placement (`woocommerce_payment_complete` or status transition to `processing`). Stock is restored on order cancellation and refund (when "Restock refunded items" is selected). **Custom code that modifies stock must use `wc_update_product_stock()` or `$product->set_stock_quantity()` + `$product->save()`** — never direct meta updates.

### Hold Stock

**Configure Hold stock (minutes)** in WooCommerce > Settings > Products > Inventory to prevent overselling during checkout. This setting reserves stock for unpaid orders (`pending` status) for the configured duration, after which unpaid orders auto-cancel and stock is restored. **Set the hold time to match the payment gateway's expected completion time** (30-60 minutes for most card payments, longer for bank transfers).

### Flash Sale Reservation

For high-traffic flash sales, implement a reservation system that **holds stock before the order is created** (at add-to-cart time) to prevent overselling during checkout processing. WooCommerce's default stock reduction occurs at payment completion, which means the same last unit can be "sold" to multiple concurrent customers whose checkouts overlap. Plugins like WooCommerce Stock Manager or custom Action Scheduler-based reservation logic address this gap.

### Stock Display

Configure low stock and out-of-stock thresholds per product. Set notification recipients to operations/fulfillment teams. **For headless frontends, check stock status via the Store API product response** (`stock_status`: `instock | outofstock | onbackorder`) before rendering add-to-cart controls. Display real-time stock quantities only if the business model requires it — exposing exact stock counts can drive urgency but also reveals inventory strategy to competitors.

---
[Back to Overview](./OVERVIEW.md)
