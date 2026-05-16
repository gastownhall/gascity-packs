# WooCommerce Development and Integration Library

**Runtime:** WooCommerce 9.0+, WordPress 6.4+, PHP 8.1+, HPOS enabled, Store API v1, WC REST API v3.

Defines strict conventions for WooCommerce order lifecycle management, High-Performance Order Storage (HPOS), REST API and Store API usage, webhook architecture, custom product types, payment gateway integration, cart and session handling for headless frontends, inventory management, subscription billing, tax and shipping configuration, and extension development. Applies to monolithic WordPress/WooCommerce installations, headless architectures with decoupled frontends (Nuxt, Next.js, React), WooCommerce as a backend commerce engine for mobile applications, and multi-site WooCommerce networks.

## Critical Mandates (Read First)

- **WooCommerce Is the Commerce Engine** — Every commercial calculation runs server-side through WooCommerce's pipeline; frontend applications render what WooCommerce reports.
- **HPOS Is the Present, Not the Future** — All new code must be HPOS-compatible; direct queries against `wp_posts` and `wp_postmeta` for order data are deprecated.
- **Hooks Are the API** — Custom logic attaches to hooks rather than overriding core methods, replacing templates wholesale, or querying the database directly.
- **Two APIs, Two Audiences** — WC REST API (`wc/v3`) for server-to-server integrations, Store API (`wc/store/v1`) for customer-facing applications. Mixing them creates security vulnerabilities.
- **Order State Is Webhook-Driven** — Systems that depend on order state subscribe to webhooks and react to confirmed transitions, not to checkout form submissions or API call return values.
- **CRUD-Only Order Access** — All order data access uses WooCommerce's CRUD layer; direct SQL queries against order tables are prohibited.
- **Shakedown Required** — Drive a real transaction through the full pipeline against a real sandbox payment gateway after every triggering change.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [High-Performance Order Storage (HPOS)](./HPOS.md)
3. [Order Lifecycle and State Management](./ORDER_LIFECYCLE.md)
4. [WC REST API (wc/v3)](./WC_REST_API.md)
5. [Store API (wc/store/v1)](./STORE_API.md)
6. [Cart and Session Handling for Headless Frontends](./CART_SESSION.md)
7. [Webhook Architecture](./WEBHOOKS.md)
8. [Custom Product Types](./CUSTOM_PRODUCT_TYPES.md)
9. [Payment Gateway Integration](./PAYMENT_GATEWAYS.md)
10. [Inventory and Stock Management](./INVENTORY.md)
11. [Subscription and Recurring Billing](./SUBSCRIPTIONS.md)
12. [Tax and Shipping Configuration](./TAX_SHIPPING.md)
13. [Email and Notification Management](./EMAIL.md)
14. [Performance Optimization](./PERFORMANCE.md)
15. [Shakedown — End-to-End Commerce Validation](./SHAKEDOWN.md)
16. [Security](./SECURITY.md)
17. [Extension Development Patterns](./EXTENSIONS.md)
18. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
19. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
20. [Required Practices](./REQUIRED_PRACTICES.md)
21. [Style Summary](./STYLE_SUMMARY.md)
