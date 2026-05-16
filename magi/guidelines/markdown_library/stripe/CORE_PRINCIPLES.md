# Core Principles

### Stripe Is the Ledger of Record

Stripe owns payment state. Local databases store **references** (Stripe IDs, metadata snapshots) for query performance and domain enrichment, but **Stripe is the authoritative source** for payment status, subscription state, invoice amounts, and dispute outcomes. When local state conflicts with Stripe state, **Stripe wins**. Reconciliation flows detect and correct drift, not override Stripe.

### Server-Side Authority

All payment-critical operations execute server-side: creating PaymentIntents, confirming payments, issuing refunds, managing subscriptions, processing webhooks. The client collects payment details via Stripe Elements and confirms payments using client secrets — but **never creates charges, modifies amounts, or accesses secret API keys**. The client is an untrusted rendering layer for Stripe's secure iframe components.

### Idempotency Everywhere

Every mutating Stripe API call (POST, DELETE) **must include an idempotency key**. Network failures, timeouts, and retries are expected conditions. Without idempotency keys, a retried charge request creates a duplicate charge. With idempotency keys, Stripe returns the original response. **This is not optional.** Every integration that skips idempotency keys will eventually double-charge a customer.

### PCI Scope Minimization

Raw card numbers, CVVs, and full magnetic stripe data **never touch your servers, logs, databases, or client-side JavaScript**. Stripe Elements and Checkout Sessions collect payment details within Stripe-hosted iframes. Your systems handle only Stripe tokens, PaymentMethod IDs, and client secrets. This keeps you at **SAQ A or SAQ A-EP** compliance level rather than the full **SAQ D** that direct card handling requires. Every architectural decision that could expose raw card data must be rejected.

### Webhook-Driven State Transitions

Payment outcomes are asynchronous. **A PaymentIntent creation does not mean payment succeeded.** Bank transfers, 3D Secure challenges, delayed payment methods, and network processing all introduce lag between intent creation and final outcome. Webhooks deliver the authoritative outcome. Design systems to react to webhook events as the **primary state transition mechanism**, not as a backup notification channel.

### The Golden Rule

**Never trust client-reported payment status.** The server creates the intent, Stripe processes the payment, and a verified webhook confirms the outcome. **Any other flow is a security vulnerability.** This applies to all payment methods, all integration patterns, and all deployment environments.

---
[Back to Overview](./OVERVIEW.md)
