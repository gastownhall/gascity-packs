# Reconciliation and Reporting

### Reconciliation Patterns

Run periodic reconciliation between local order/subscription state and Stripe's state:

- Compare local payment records against Stripe's PaymentIntent list.
- Identify:
  - **Orphaned local records** (no matching Stripe object).
  - **Orphaned Stripe objects** (charge with no local order).
  - **State mismatches** (local says paid, Stripe says refunded).
- Schedule reconciliation **daily** during low-traffic hours.
- Alert on discrepancies. Provide tooling for operations to resolve mismatches.
- **Reconciliation catches** webhook delivery failures, processing bugs, manual Dashboard actions that bypass application logic.

### Financial Reporting

Use Stripe's **Reporting API** and **Dashboard exports** for financial reporting:

- The **Balance Transactions API** is the authoritative record of money movement: charges, refunds, fees, transfers, payouts.
- Map balance transactions to internal accounting categories.
- **Stripe Sigma** provides SQL-based querying across all Stripe data for custom reports.
- For tax reporting, integrate **Stripe Tax** or export transaction data with `tax_amounts`.
- Store the Stripe `balance_transaction` ID with every local financial record for **audit traceability**.

---
[Back to Overview](./OVERVIEW.md)
