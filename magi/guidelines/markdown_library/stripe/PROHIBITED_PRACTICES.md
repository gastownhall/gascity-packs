# Prohibited Practices

### Never Do

- Expose secret keys (`sk_*`) in client-side code, mobile apps, version control, or CI logs. **Full API access compromise.**
- Transmit, store, process, or log raw card numbers, CVVs, or full expiration dates on your systems. **PCI violation.**
- Process webhook payloads without `Stripe-Signature` verification. **Enables forged payment confirmations.**
- Make mutating Stripe API calls without idempotency keys. **Guarantees duplicate charges on retry.**
- Allow the client to specify payment amounts. **Price manipulation vulnerability.**
- Grant access to purchased content based on success URL navigation. **Bypassed by direct URL access.**
- Ignore dispute notifications or miss evidence submission deadlines. **Automatic loss plus fee.**
- Use live keys in development or staging. **Risk of accidental real charges during testing.**
- Self-host `stripe.js` instead of loading from `js.stripe.com`. **PCI compliance violation and misses security updates.**
- Use the legacy Charges API for new integrations. **PaymentIntents API is required for SCA compliance.**
- Parse the webhook request body as JSON before signature verification. **Breaks signature validation.**
- Retry `card_error` or `validation_error` responses. **Deterministic failures.**
- Make API calls without pinning an API version. **Behavior changes silently on account version updates.**
- Create Stripe objects without metadata. **Reconciliation and debugging become significantly harder.**
- Skip the §13 shakedown after a triggering change.
- Run shakedown against `stripe-mock`, recorded fixtures, or live mode.

---
[Back to Overview](./OVERVIEW.md)
