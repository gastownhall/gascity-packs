# PCI Compliance and Scope Reduction

### PCI Scope Levels

| Level | Description | Burden |
|:------|:------------|:-------|
| **SAQ A** | Fully outsourced payment page (Stripe Checkout redirect or Stripe-hosted payment links). Your servers never serve a page containing payment fields | **Lowest** |
| **SAQ A-EP** | Your page embeds Stripe Elements iframes. Your server serves the page, but card data enters only the Stripe iframe | **Standard** for custom checkout UIs |
| **SAQ D** | Your systems handle raw card data — required if you use the Charges API with direct tokenization, log card details, or transmit PAN | **Maximum — avoid at all costs** |

**No system under this organization's control transmits, stores, processes, or logs raw card numbers, CVVs, expiration dates, or magnetic stripe data.** All card collection uses Stripe Elements or Stripe Checkout. Violations require immediate PCI incident response.

### Stripe Elements Security Model

Stripe Elements renders payment input fields inside **cross-origin iframes hosted on Stripe's domain** (`js.stripe.com`). Your page JavaScript cannot read the contents of these iframes. Card data travels directly from the Stripe iframe to Stripe's servers, **bypassing your infrastructure entirely**.

This architectural boundary is the foundation of PCI scope reduction. Do not attempt to:

- Style Elements by injecting CSS into the iframe.
- Read values from the iframe via DOM traversal.
- Intercept the iframe's network requests.

All of these violate the security model and may void PCI compliance.

### Logging Restrictions

- **Never log full card numbers, CVVs, or complete expiration dates.**
- Stripe API responses include card details as objects with only `last4`, `brand`, and `exp_month`/`exp_year` — these truncated values are safe to log and store.
- If a logging framework captures full request/response bodies from Stripe API calls, verify no response contains full card data.
- **Mask Stripe secret keys in logs.** Log publishable keys only when debugging client initialization issues.

### Content Security Policy for Stripe

Required CSP directives:

| Directive | Hosts |
|:----------|:------|
| `frame-src` | `js.stripe.com`, `hooks.stripe.com`, `checkout.stripe.com` (for Checkout redirects) |
| `script-src` | `js.stripe.com` |
| `connect-src` | `api.stripe.com` |

Overly restrictive CSP blocks Stripe's iframes and breaks payment collection. Test CSP changes against all payment flows before deploying to production.

---
[Back to Overview](./OVERVIEW.md)
