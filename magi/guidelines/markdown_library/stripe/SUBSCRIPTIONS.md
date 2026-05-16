# Subscriptions and Billing

### Subscription Lifecycle

| Status | Access |
|:-------|:-------|
| `trialing` | Trial period active, no charge — full access |
| `active` | Payment succeeded — full access |
| `past_due` | Payment failed, retrying — grace period access with payment prompt |
| `unpaid` | All retries exhausted — revoked access |
| `canceled` | Terminated — revoked access |
| `paused` | Paused billing — application-defined behavior |

Map each status to an application access level. Transition logic lives in webhook handlers for `customer.subscription.updated` and `invoice.paid`/`invoice.payment_failed`.

### Subscription Creation Patterns

- Create subscriptions **server-side** via the Subscriptions API or via Checkout Sessions in subscription mode.
- Attach a default PaymentMethod to the Customer **before** creating the subscription, or provide it in the subscription creation call.
- For trial periods, set `trial_period_days` or `trial_end`.
- **Collect payment details upfront via SetupIntent even for trials** — reduces involuntary churn when the trial converts to paid because the payment method is already on file and validated.

### Invoice Handling

Stripe generates invoices automatically for subscription billing cycles.

| Status | Meaning |
|:-------|:--------|
| `draft` | Editable |
| `open` | Finalized, payment pending |
| `paid` | Successful |
| `uncollectible` / `void` | Failed terminally |

- Use `invoice.paid` as the **definitive signal** that a billing period is covered.
- Do not rely on subscription status alone — a subscription can be `active` while the latest invoice is still processing.
- **Metered billing:** report usage via Subscription Items **before** the billing period ends. Late usage reports miss the invoice and are not billed until the next cycle.

### Failed Payment Recovery (Dunning)

- Configure Stripe's **Smart Retries** in Billing Settings to automatically retry failed subscription payments with optimized timing.
- Configure `subscription_settings.default_payment_behavior` and the number of retry attempts.
- After all retries exhaust, the subscription transitions to `unpaid` or `canceled` based on configuration.
- Send customer-facing emails on `invoice.payment_failed` with a link to update their payment method (Customer Portal or a custom update page using a SetupIntent).
- Track recovery rates in Stripe's Revenue Recovery dashboard.

### Plan Changes and Proration

Configure `proration_behavior` when updating a subscription:

| Behavior | Effect |
|:---------|:-------|
| `create_prorations` (default) | Generates credit/debit line items on the next invoice |
| `none` | No adjustment — use for plan changes effective at period end |
| `always_invoice` | Generate and charge a prorated invoice immediately |

**Preview proration amounts via the Upcoming Invoice API** before confirming changes — show the customer the adjusted amount before they commit.

### Customer Portal

Stripe's **Customer Portal** provides a hosted UI for customers to manage subscriptions, update payment methods, view invoice history, cancel.

- Configure allowed actions in the Stripe Dashboard.
- Create portal sessions server-side and redirect the customer.
- Reduces custom development for self-service account management.
- Handles SCA for payment method updates and generates the appropriate webhook events.

---
[Back to Overview](./OVERVIEW.md)
