# Style Summary

| Element | Required pattern |
|:--------|:-----------------|
| **HPOS** | Enabled and authoritative; CRUD-only access; declare compatibility in all extensions; migrate via compatibility mode with CLI sync; verify data integrity post-migration |
| **Order Lifecycle** | Status transitions via `update_status()`; `payment_complete` for fulfillment triggers; idempotent webhook handlers; order notes for audit trail; concurrency guards for parallel processing |
| **WC REST API** | Authenticated with consumer key/secret over HTTPS; scoped permissions per integration; pinned API version; paginated list endpoints; rate-limited clients; batch operations for bulk |
| **Store API** | Unauthenticated, session-scoped; `Cart-Token` for headless; no `Nonce` with `Cart-Token`; product catalog for display; cart/checkout for customer operations; never use for admin functions |
| **Cart/Session (Headless)** | `Cart-Token` header from first `/cart` GET; persist token in frontend cookie/store; handle session expiry gracefully; CORS configured with token exposure; no mixed checkout modes; cart merging requires server-side user identity |
| **Webhooks** | Verify signature before processing; deduplicate by delivery ID; return 200 within seconds; process async; monitor delivery health; pin API version in payload format |
| **Custom Product Types** | Extend `WC_Product`; class name matches type slug; register via `product_type_selector` and `woocommerce_product_class`; custom add-to-cart templates; HPOS-compatible meta storage |
| **Payment Gateways** | Extend `WC_Payment_Gateway`; `process_payment` returns redirect; confirm via webhook; implement `process_refund`; declare block checkout compatibility; never handle raw card data |
| **Inventory** | CRUD stock updates only; hold stock for pending orders; reservation system for flash sales; low stock notifications to operations; real-time stock in Store API responses |
| **Subscriptions** | Subscriptions API for all operations; handle renewal failures with retry; customer payment update flows; test lifecycle in staging; hook-driven downstream reactions |
| **Tax/Shipping** | Automated tax for multi-jurisdiction; server-side calculation only; zone-based shipping from specific to general; carrier API plugins for real-time rates |
| **Performance** | HPOS enabled; persistent object cache; page cache excludes cart/checkout/my-account; Action Scheduler retention managed; headless catalog caching with webhook invalidation |
| **Security** | HTTPS everywhere; tokenized payments; IP-restricted admin API; rate-limited Store API; capability audits; no consumer keys in client code |
| **Extensions** | HPOS declared; WC active check; documented API only; WC logger for logging; QIT for marketplace testing; version compatibility headers |
| **Shakedown** | Real sandbox gateway only; six validation categories; fixture-versioned canary product/coupon/address/card; pass/fail-blocking/fail-nonblocking/inconclusive; four required artifacts |
| **Defense in Depth** | Staging mirror + backups + update discipline + gateway monitoring + perf monitoring + reconciliation + integrity scans = seven independent layers; synthetic checkout + gateway webhook + reconciliation = the Rule of Three quorum |

---

**Apply these guidelines universally to all WooCommerce development and integration work.**

---
[Back to Overview](./OVERVIEW.md)
