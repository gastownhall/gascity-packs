# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Core Architecture | Stripe is the ledger of record; server-side authority for all mutations; webhook-driven state transitions; client is untrusted rendering layer |
| Key Management | Secret keys server-only; publishable keys client-only; restricted keys for services; test/live separation enforced at startup; rotate quarterly |
| Webhooks | Verify signature with raw body; return 200 fast; process async; deduplicate by `event.id`; monitor delivery health; handle all subscribed event types |
| Idempotency | Deterministic keys from business context on every mutation; same key for retries; one key per operation type; keys on webhook-triggered API calls too |
| PCI | Elements or Checkout for card collection; never touch raw card data; SAQ A or SAQ A-EP; CSP allows `js.stripe.com`; no PAN in logs |
| Payments | Server creates PaymentIntents with amount; client confirms via Elements; handle `requires_action` for SCA; metadata on every object; amounts in smallest unit |
| Subscriptions | Map status to access; collect payment method before trials; webhook-driven lifecycle; configure Smart Retries; test clocks for billing cycle testing |
| Refunds / Disputes | Idempotent refund issuance; validate remaining amount; respond to every dispute; automate evidence collection; statement descriptor for prevention |
| Error Handling | Classify by type; retry only network/server errors; backoff exponentially; built-in SDK retries; circuit breaker for high-throughput; monitor Stripe status |
| Testing | Test mode for all non-production; Stripe CLI for webhook testing; test cards for every outcome; Test Clocks for subscriptions; clean up test data |
| Reconciliation | Daily reconciliation between local and Stripe state; `balance_transaction` IDs for audit; metadata for traceability; alert on discrepancies |
| Shakedown | Real test-mode API + real webhook signatures + real Test Clocks; pass / fail-blocking / fail-nonblocking / inconclusive; four artifacts mandatory |
| Defense in Depth | Idempotency + signature verification + webhook source of truth + nightly reconciliation + retry-with-backoff + dispute monitoring + test-mode parity |
| Rule of Three | API response + webhook event + reconciliation row MUST agree before declaring revenue recognized |

---
[Back to Overview](./OVERVIEW.md)
