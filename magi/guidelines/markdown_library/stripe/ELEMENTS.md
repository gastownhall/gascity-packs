# Stripe Elements Embedding

### Elements Initialization

- Load Stripe.js via the `@stripe/stripe-js` package (`loadStripe()`) or the script tag from `js.stripe.com`.
- **Never self-host `stripe.js`** — Stripe requires the script to load from their CDN for PCI compliance and feature updates.
- Initialize the Elements instance with the publishable key and optional configuration (appearance, locale, fonts).

| Concern | Practice |
|:--------|:---------|
| SSR (Nuxt, Next.js) | Load Stripe.js only on the client. Guard with `import.meta.client` or `onMounted` |
| Single instance | Create one Stripe instance per page. Multiple `loadStripe()` calls create multiple iframe contexts and degrade performance |

### Payment Element

The **Payment Element** is the recommended integration for collecting payment details. Renders a single, adaptive UI supporting cards, wallets (Apple Pay, Google Pay), bank transfers, BNPL, and region-specific methods. It adapts to the customer's location and the PaymentIntent's `payment_method_types` configuration.

Use the Payment Element instead of individual Card Element, IBAN Element, or Ideal Element integrations unless a specific UX requirement demands granular control.

### Appearance Customization

Customize via the **appearance API** (theme, variables, rules) passed during initialization:

- Controls colors, fonts, spacing, borders, focus states.
- Custom fonts load via the `fonts` array in the Elements constructor.
- Style the container `<div>` (size, padding, background) with your own CSS.
- **Do not attempt to style the iframe contents via CSS injection** — does not work and is a PCI violation.
- Test appearance across browsers, mobile viewports, dark/light modes.

### Element Events and Error Handling

Elements emit events: `change` (field value changed), `ready` (Element mounted), `focus`, `blur`, `escape`, `loaderror`.

- The `change` event includes error information for real-time validation (incomplete card number, invalid expiration, missing CVC).
- Display errors from `change` below the Element component.
- Disable the submit button while the Element is incomplete or has errors.
- Handle `loaderror` for cases where the Element fails to load (network issues, script blocking, CSP violations).

### Stripe Checkout (Hosted)

Stripe Checkout provides a **Stripe-hosted payment page**:

1. Server creates a Checkout Session with line items, success/cancel URLs, configuration.
2. Client redirects to the Checkout URL.
3. Stripe handles the entire payment UI, SCA, and payment method selection.
4. On completion, Stripe redirects to the success URL and fires `checkout.session.completed`.

**SAQ A compliance** — the payment page is entirely Stripe-hosted. Use Checkout when custom payment UI is not a business requirement.

| Constraint | Behavior |
|:-----------|:---------|
| Success URL | **Must not grant access to purchased content.** Attackers can navigate directly to the success URL without paying. Use `checkout.session.completed` to provision access. The success URL is a thank-you page, not an access gate |
| Session expiry | Checkout Sessions expire after 24 hours by default (configurable to 30 minutes minimum). Expired sessions fire `checkout.session.expired` — release any reserved inventory |

---
[Back to Overview](./OVERVIEW.md)
