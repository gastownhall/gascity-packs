# Core Principles

### WooCommerce Is the Commerce Engine

WooCommerce manages the transactional truth: product catalog, pricing, inventory, orders, payments, refunds, taxes, and shipping. Whether the frontend is a traditional WordPress theme, a Nuxt SPA, or a mobile app, **WooCommerce is the authoritative system for commerce state**. Frontend applications render what WooCommerce reports. They do not compute prices, apply discounts, or determine tax independently. **Every commercial calculation runs server-side through WooCommerce's pipeline.**

### HPOS Is the Present, Not the Future

High-Performance Order Storage is the default for new WooCommerce installations since 8.2 (October 2023) and the foundation for all future WooCommerce development. **All new code must be HPOS-compatible.** All existing code must migrate to HPOS-compatible patterns. Direct queries against `wp_posts` and `wp_postmeta` for order data are deprecated. The CRUD layer (`wc_get_orders`, `WC_Order` methods, `WC_Order_Query`) is the only supported interface for order operations.

### Hooks Are the API

WooCommerce's action and filter system is the primary extension mechanism. The order lifecycle, cart operations, checkout processing, payment handling, and email dispatch all fire hooks at every significant state transition. **Custom logic attaches to these hooks rather than overriding core methods, replacing templates wholesale, or querying the database directly.** When a hook does not exist for a needed behavior, the correct response is to request one upstream — not to bypass the hook system.

### Two APIs, Two Audiences

| API | Authentication | Audience | Purpose |
|:----|:---------------|:---------|:--------|
| **WC REST API** (`wc/v3`) | Authenticated | Server-to-server | Full read/write to store data; admin and integration |
| **Store API** (`wc/store/v1`) | Unauthenticated, session-scoped | Customer-facing | Cart, checkout, product data scoped to current session |

**Mixing these APIs or using the admin API for customer-facing features creates security vulnerabilities and architectural coupling.**

### Order State Is Webhook-Driven

Payment outcomes, refund completions, and subscription transitions are **asynchronous**. A checkout submission does not mean payment succeeded. A refund request does not mean funds returned. **Webhooks deliver authoritative state changes** from payment gateways and WooCommerce's internal processing. Systems that depend on order state (fulfillment, access provisioning, analytics) subscribe to webhooks and react to **confirmed transitions** — not to checkout form submissions or API call return values.

### Hard Rules (Core)

- **All order data access uses WooCommerce's CRUD layer** — `wc_get_order()`, `wc_get_orders()`, `WC_Order_Query`, and `WC_Order` getter/setter methods. Direct SQL queries against `wp_posts`, `wp_postmeta`, or HPOS tables (`wp_wc_orders`, `wp_wc_order_addresses`, `wp_wc_orders_meta`) are prohibited in plugin and theme code.
- **Every custom plugin that reads, writes, or queries order data declares HPOS compatibility** via `FeaturesUtil::declare_compatibility('custom_order_tables', __FILE__, true)` in the `before_woocommerce_init` action. Undeclared plugins trigger compatibility warnings and may force WooCommerce to disable HPOS or enable compatibility mode, negating its performance benefits.

---
[Back to Overview](./OVERVIEW.md)
