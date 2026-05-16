# Refunds and Disputes

### Refund Processing

- Issue refunds **server-side** via the Refunds API with the PaymentIntent ID or Charge ID and the refund amount.
- Support full and partial refunds.
- Include an idempotency key derived from order ID + refund request to prevent duplicate refunds on retry.
- Include metadata with refund reason, initiator (customer request, admin action, automated rule), internal reference.
- Refunds for card payments typically take **5–10 business days** to appear on the customer's statement — communicate this to the customer.

| Constraint | Detail |
|:-----------|:-------|
| Timing | Refunds can only be issued on charges **less than 180 days old** (varies by payment method). After this window, use your own disbursement method (bank transfer, store credit) |
| Amount | Must not exceed the original charge minus any previous refunds. Validate the remaining refundable amount before issuing |
| Accounting | Refunds **do not** reverse Stripe's processing fees for the original charge (fees are returned for full refunds on most payment methods, but not all). Account for net revenue after fees in financial reconciliation |

### Dispute (Chargeback) Handling

Disputes occur when a cardholder contests a charge with their bank. Stripe notifies via `charge.dispute.created`.

**Dispute lifecycle:**

1. Evidence submission window opens (typically 7–21 days depending on card network).
2. You submit evidence.
3. The bank reviews.
4. Dispute closes as **won** (charge upheld) or **lost** (charge reversed plus dispute fee).

**Dispute fees ($15 USD for most networks) apply regardless of outcome.**

**Respond to every dispute within the evidence submission deadline.** Uncontested disputes are automatically lost. Even for disputes you expect to lose, submitting evidence demonstrates good-faith processing and may influence the issuing bank's fraud scoring for future transactions.

### Evidence Preparation

Stripe's Dispute object includes an `evidence` sub-object with fields for:

- Customer communication
- Shipping documentation
- Service documentation
- Policy information

**Pre-populate as much evidence as possible programmatically** when the dispute is created. Automate evidence collection: pull order details, delivery confirmation, customer email correspondence, IP address logs, terms-of-service acceptance timestamps. Include the customer's name, email, billing-address match information.

**Automated evidence submission within hours of dispute creation dramatically improves win rates** compared to manual evidence gathering.

### Dispute Prevention

| Practice | Effect |
|:---------|:-------|
| Use Stripe Radar for fraud detection | Catches suspicious charges before they post |
| Set `statement_descriptor` to a recognizable business name | Unrecognized charges drive friendly fraud disputes |
| Send order confirmation emails immediately | Customers know what they paid for |
| Provide easy-to-find refund and cancellation flows | Customers who cannot easily get a refund open disputes instead |
| Implement Stripe's Early Fraud Warning (EFW) webhook (`radar.early_fraud_warning.created`) | Proactively refund suspicious charges before they become disputes |

---
[Back to Overview](./OVERVIEW.md)
