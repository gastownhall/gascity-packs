# Required Practices

### Always Do

- **Declare HPOS compatibility** in all extensions. Use CRUD methods exclusively for order data.
- Access all order, product, and customer data via WooCommerce CRUD methods, **never direct SQL**.
- Use the Store API (`wc/store/v1`) for all customer-facing cart and checkout operations in headless architectures.
- Use `Cart-Token` headers for session management in headless frontends. **Persist tokens across navigation.**
- Verify `X-WC-Webhook-Signature` on every incoming webhook. **Reject unverified payloads.**
- Deduplicate webhook deliveries by delivery ID. Process asynchronously. **Return 200 fast.**
- Process all payment operations server-side via `WC_Payment_Gateway`. **Never trust client-reported payment status.**
- Transition order status via `$order->update_status()` or `set_status()/save()`. **Never modify status directly.**
- Add order notes for every significant automated action with system identifier and reference IDs.
- Configure CORS with specific origin whitelist and **expose `Cart-Token` in response headers** for headless frontends.
- Enforce HTTPS on all WooCommerce pages, APIs, webhooks, and admin interfaces.
- Route all transactional email through a dedicated email service, **not PHP `mail()`**.
- Deploy persistent object caching (Redis/Memcached) for WooCommerce transient and cache optimization.
- Declare `WC requires at least`, `WC tested up to`, and feature compatibility in all extension headers.
- Test HPOS migration, payment flows, subscription renewals, and webhook processing in staging before production.
- Run shakedown after every triggering change against real sandbox payment gateway.
- Capture all required shakedown artifacts (execution log, result summary, order fixtures, environment snapshot).

---
[Back to Overview](./OVERVIEW.md)
