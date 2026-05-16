# Payment Intents and Payment Lifecycle

### PaymentIntent Lifecycle

The PaymentIntent is the core object for payment processing.

| Status | Meaning |
|:-------|:--------|
| `requires_payment_method` | Created, awaiting card |
| `requires_confirmation` | Payment method attached, awaiting confirmation |
| `requires_action` | 3D Secure or redirect required |
| `processing` | Payment is being processed by the network |
| `succeeded` | Payment complete |
| `canceled` | Canceled |

**Server creates the PaymentIntent** with amount, currency, and metadata. Client confirms using the `client_secret`. Stripe processes and delivers the outcome via webhook.

**The server creates PaymentIntents with the authoritative amount, currency, and metadata. The client never specifies the amount.** A client-controlled amount enables price manipulation — the customer changes $100 to $1 in the browser and submits.

### Payment Method Handling

Use the **PaymentIntent + PaymentMethod** flow (not the legacy Charges + Tokens flow):

- Collect payment details via Elements, which creates a PaymentMethod object.
- Attach the PaymentMethod to the PaymentIntent during confirmation.
- For returning customers, attach PaymentMethods to the Customer object for reuse.
- Store the Stripe PaymentMethod ID locally for reference, **never** raw card details.
- **The legacy Charges API and Token-based flow are deprecated for new integrations.**

### 3D Secure (SCA) Handling

Strong Customer Authentication (SCA) is required for European card payments and increasingly applied globally.

- When a PaymentIntent requires 3D Secure, its status transitions to `requires_action`.
- The client calls `stripe.handleNextAction()` or `stripe.confirmPayment()` which opens the bank's authentication challenge.
- The customer completes authentication; Stripe updates the PaymentIntent status; webhook delivers the final outcome.
- **Design the checkout flow to handle `requires_action` as a normal case, not an exception.** Approximately 20–40% of European transactions require SCA.

### Metadata Strategy

Attach metadata to **every** Stripe object (PaymentIntents, Customers, Subscriptions, Invoices):

- `order_id`, `user_id`, `plan_name`, `promotion_code`, `internal_reference`.
- Stripe does not interpret metadata — it stores and returns it.
- Metadata is invaluable for reconciliation, debugging, analytics.
- **Limits:** maximum 50 keys, 500-character key names, 500-character values.
- **Do not store sensitive data (PII, credentials)** in metadata — visible to anyone with Dashboard or API access.

### Currency Handling

**Stripe represents amounts in the smallest currency unit:** cents for USD/EUR, yen for JPY. Sending `1000` in USD charges $10.00, **not** $1,000.00. Zero-decimal currencies (JPY, KRW) use the full amount.

This is the **most common source of amount errors** in Stripe integrations.

- Centralize the conversion between display amounts and Stripe amounts in a single utility function.
- **Validate that Stripe amounts are positive integers** before API submission. Amounts of zero are valid only for setup intents and trials. Negative amounts are invalid. Floating-point amounts indicate a conversion bug (e.g., passing `10.99` instead of `1099`).
- Store the Stripe amount (integer, smallest unit) alongside the display amount and currency code in your database for unambiguous reconciliation.

---
[Back to Overview](./OVERVIEW.md)
