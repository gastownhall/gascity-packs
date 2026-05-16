# Required Practices

### Always Do

- Verify `Stripe-Signature` on every webhook request using the **raw body** before any processing.
- Include **deterministic idempotency keys** on every mutating API call (POST, DELETE).
- Create PaymentIntents, Subscriptions, and Checkout Sessions **server-side** with server-controlled amounts.
- Collect payment details exclusively via Stripe Elements or Stripe Checkout. **Never handle raw card data.**
- Use webhooks as the **primary mechanism** for payment outcome processing and fulfillment triggers.
- Deduplicate webhook events by `event.id` before processing business logic.
- Pin the Stripe API version in SDK initialization and on webhook endpoints.
- Attach metadata (`order_id`, `user_id`, context) to all Stripe objects for reconciliation.
- Use test keys for dev/staging and live keys for production exclusively. **Validate key-environment match at startup.**
- Use restricted API keys with minimum required permissions for single-purpose services.
- Handle `requires_action` status for 3D Secure as a **standard checkout flow path**, not an error.
- Represent all amounts in **smallest currency unit** (cents). Centralize conversion. Validate as positive integers.
- Submit evidence for every dispute within the deadline. Automate evidence collection.
- Use Stripe **Test Clocks** for subscription lifecycle testing. Never rely on real-time waiting.
- Run automated reconciliation between local state and Stripe state. Alert on discrepancies.
- Run a §13 shakedown after every triggering change before live-mode cutover.

---
[Back to Overview](./OVERVIEW.md)
