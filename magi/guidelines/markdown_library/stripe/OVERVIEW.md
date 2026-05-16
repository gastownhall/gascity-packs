# Stripe Integration Library

**Runtime:** Stripe API version 2024-12-18+, `stripe-node` 17+, `@stripe/stripe-js` 4+, `@stripe/react-stripe-js` 3+ (or framework equivalent).

**Scope:** All backend services, frontend clients, and infrastructure that interact with the Stripe API — direct integrations (API-first), Stripe Elements, Checkout Sessions, Billing, Connect, and webhook consumers.

## Critical Mandates (Read First)

- **Stripe Is the Ledger of Record** — Stripe owns payment state; local databases store references for query performance and domain enrichment, but Stripe is the authoritative source. When local state conflicts with Stripe state, **Stripe wins**.
- **Server-Side Authority** — All payment-critical operations execute server-side; the client never creates charges, modifies amounts, or accesses secret API keys.
- **Idempotency Everywhere** — Every mutating Stripe API call must include an idempotency key. **This is not optional.** Every integration that skips idempotency keys will eventually double-charge a customer.
- **PCI Scope Minimization** — Raw card numbers, CVVs, and full magnetic stripe data never touch your servers, logs, databases, or client-side JavaScript.
- **Webhook-Driven State Transitions** — Payment outcomes are asynchronous; design systems to react to webhook events as the primary state transition mechanism.
- **The Golden Rule** — Never trust client-reported payment status. Any other flow is a security vulnerability.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [API Key Management](./API_KEY_MANAGEMENT.md)
3. [Webhook Security and Processing](./WEBHOOK_SECURITY.md)
4. [Idempotency](./IDEMPOTENCY.md)
5. [PCI Compliance and Scope Reduction](./PCI_COMPLIANCE.md)
6. [Payment Intents and Payment Lifecycle](./PAYMENT_INTENTS.md)
7. [Stripe Elements Embedding](./ELEMENTS.md)
8. [Subscriptions and Billing](./SUBSCRIPTIONS.md)
9. [Refunds and Disputes](./REFUNDS_DISPUTES.md)
10. [Stripe Connect](./CONNECT.md)
11. [Error Handling and Resilience](./ERROR_HANDLING.md)
12. [Testing](./TESTING.md)
13. [Shakedown — Integration Validation](./SHAKEDOWN.md)
14. [Reconciliation and Reporting](./RECONCILIATION.md)
15. [API Versioning and Upgrades](./API_VERSIONING.md)
16. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
17. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
18. [Required Practices](./REQUIRED_PRACTICES.md)
19. [Style Summary](./STYLE_SUMMARY.md)
