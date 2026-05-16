# Idempotency

### Idempotency Key Strategy

Every mutating Stripe API call (creating PaymentIntents, Customers, Subscriptions, Refunds, Transfers) includes an `Idempotency-Key` header. Stripe caches the response for **24 hours** keyed by this value. Retries with the same key return the cached response without re-executing the operation. GET requests are inherently idempotent and do not need keys.

### Key Generation Rules

- **Deterministic, business-context derived** — for a checkout: `hash(user_id + cart_id + cart_version)`. For a refund: `hash(order_id + refund_reason + amount)`.
- **Random UUIDs per request defeat the purpose** — a retry generates a new UUID and creates a duplicate operation.
- **One key per distinct business operation.** Do not reuse keys across different operation types. A key used for PaymentIntent creation must not be reused for Refund creation, even if related to the same order.
- **Format:** unique strings up to 255 characters; include enough context to be deterministic — entity ID, operation type, version/timestamp component that changes when parameters change (different amount = different key).
- **Retry safety:** when a Stripe API call times out or returns a network error, **retry with the same idempotency key**. Never generate a new key for a retry.

### Idempotency in Webhook Processing

Webhook idempotency is **separate** from API call idempotency.

- Webhook handlers deduplicate based on `event.id` to prevent double-processing of the same event.
- API calls made within webhook handlers (e.g., fulfilling an order by calling an internal API) **must themselves be idempotent**.
- A webhook handler that calls a non-idempotent fulfillment API on each invocation will double-fulfill on duplicate webhook delivery despite event-level deduplication if the deduplication check races.

---
[Back to Overview](./OVERVIEW.md)
