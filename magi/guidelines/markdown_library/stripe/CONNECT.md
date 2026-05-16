# Stripe Connect

### Connect Account Types

| Type | Control | Use case |
|:-----|:--------|:---------|
| **Standard** | Connected account manages their own Stripe Dashboard, lowest platform liability | Most marketplace integrations |
| **Express** | Platform-branded onboarding, Stripe-hosted dashboard | Balance of platform control and Stripe management |
| **Custom** | Full platform control over UI and experience, highest dev and compliance burden | Platforms with specific UX requirements |

### Connect Charge Patterns

| Pattern | Mechanism |
|:--------|:----------|
| **Direct charges** | Charge created on the connected account |
| **Destination charges** | Charge on the platform, funds transferred to the connected account — most common for marketplaces; allow `application_fee_amount` for platform revenue |
| **Separate charges and transfers** | Charge on platform, explicit transfer later — use `transfer_group` to link related charges and transfers for reconciliation |

### Onboarding

Use **Account Links** for Standard and Express onboarding:

1. Create an Account Link with the account ID, redirect URLs, and type `account_onboarding`.
2. Redirect the user to the Account Link URL.
3. Stripe collects identity verification, bank account details, business information.
4. Monitor `account.updated` for requirements changes (additional verification needed, deadline approaching).

**Accounts with outstanding requirements cannot process payments** — handle the `capabilities.transfers` and `capabilities.card_payments` states in your platform logic.

---
[Back to Overview](./OVERVIEW.md)
