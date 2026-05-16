# Webhook Security and Processing

### Signature Verification

Every incoming webhook request **must verify the `Stripe-Signature` header** against the webhook signing secret using `stripe.webhooks.constructEvent()`. This verifies authenticity AND integrity.

**Use the raw request body for verification — not parsed JSON.** Parsing and re-serializing alters whitespace and key ordering, which breaks the signature.

| Framework | Raw body access |
|:----------|:----------------|
| Express | `express.raw({ type: 'application/json' })` on the webhook route |
| Nitro/H3 | `readRawBody(event)` |
| Frameworks with global JSON parsing | Exclude the webhook path |

**Signature verification executes before any business logic.** An unverified webhook payload is untrusted input from the internet. Processing unverified webhooks enables payment fraud, inventory manipulation, and unauthorized account access.

### Webhook Idempotency

Stripe may deliver the same webhook event multiple times. Network issues, timeouts, and retries cause duplicate delivery. **Every webhook handler must be idempotent.**

- Store processed event IDs in a database table or cache with TTL matching Stripe's retry window (up to **72 hours**).
- Use `event.id` as the deduplication key.
- Check for prior processing **before** executing business logic.

**Atomicity:** the deduplication check and business logic execution must be atomic or use optimistic concurrency. A race condition where two concurrent deliveries both pass deduplication and both execute results in duplicate processing despite the deduplication logic.

### Handler Patterns — Acknowledge Fast, Process Async

**Return HTTP 200 within seconds.** Stripe expects a response within 20 seconds. Stripe interprets timeouts and 5xx responses as delivery failures and retries with exponential backoff. A slow handler that consistently times out triggers repeated retries that amplify load and duplicate processing.

- Acknowledge the webhook immediately with a 2xx response.
- Enqueue the event for background processing (database queue, message broker, Action Scheduler in WordPress, BullMQ in Node).
- If synchronous processing is unavoidable, keep it under 5 seconds and return 200 even if downstream processing will continue.

### Essential Event Types

#### Payments

| Event | Action |
|:------|:-------|
| `payment_intent.succeeded` | Payment completed — fulfill the order |
| `payment_intent.payment_failed` | Payment failed — notify the customer; do not fulfill |
| `payment_intent.canceled` | PaymentIntent canceled — release held inventory |
| `charge.refunded` | Refund processed — reverse fulfillment or credit the account |
| `charge.dispute.created` | Dispute opened — pause fulfillment, gather evidence |
| `charge.dispute.closed` | Dispute resolved — apply outcome (won: no action; lost: debit) |

#### Subscriptions

| Event | Action |
|:------|:-------|
| `customer.subscription.created` | Subscription started — provision access |
| `customer.subscription.updated` | Subscription changed (plan, quantity, status) — adjust access |
| `customer.subscription.deleted` | Subscription canceled — revoke access at period end or immediately per cancellation type |
| `invoice.paid` | Invoice payment succeeded — extend access for the billing period |
| `invoice.payment_failed` | Invoice payment failed — notify customer; Stripe Smart Retries handle subsequent attempts |
| `customer.subscription.trial_will_end` | Trial ending in 3 days — notify customer about upcoming charge |

#### Checkout

| Event | Action |
|:------|:-------|
| `checkout.session.completed` | Checkout finished — retrieve line items and fulfill |
| `checkout.session.expired` | Session expired without completion — release reserved inventory |
| `checkout.session.async_payment_succeeded` | Delayed payment method (bank transfer, Boleto) succeeded after session completion |
| `checkout.session.async_payment_failed` | Delayed payment method failed — do not fulfill |

### Webhook Monitoring

- Monitor webhook delivery health in the Stripe Dashboard under **Developers > Webhooks**.
- Alert on elevated failure rates.
- Track processing latency, deduplication hit rate, handler error rate in application monitoring.
- **Stripe disables webhook endpoints after sustained delivery failures** — monitor for disabled endpoints and remediate immediately.
- Implement a dead-letter mechanism for events that fail processing after multiple attempts: log the event, alert operations, provide tooling for manual replay.

---
[Back to Overview](./OVERVIEW.md)
