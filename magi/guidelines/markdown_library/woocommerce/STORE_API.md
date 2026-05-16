# Store API (wc/store/v1)

The Store API is the **customer-facing API** designed for headless frontends, block-based checkout, and any client that needs to interact with cart, checkout, and product catalog without administrative privileges. **It is unauthenticated by design** — it does not require API keys. Session identity is managed via cookies (traditional) or `Cart-Token` headers (headless). **The Store API is the correct API for Nuxt, Next.js, React, and mobile app storefronts.**

### Cart and Checkout Endpoints

**Use the Store API for all customer-facing cart and checkout operations.** Do not use the WC REST API for cart management — it has no cart endpoints. Cart state is session-scoped and managed exclusively through:

- `/wc/store/v1/cart`
- `/wc/store/v1/cart/add-item`
- `/wc/store/v1/cart/remove-item`
- `/wc/store/v1/cart/update-item`
- `/wc/store/v1/checkout`
- `/wc/store/v1/cart/select-shipping-rate`

### Session Scoping

The Store API scopes all data to the current session. **It cannot look up other customers' carts, orders, or personal data.** Product endpoints return only publicly visible products. **This is by design** — the Store API is safe to call from untrusted client-side code because it exposes no administrative data and no cross-customer data.

### Catalog Browsing

Use the Store API's product endpoints (`wc/store/v1/products`) for catalog browsing in headless frontends. These return pricing, images, attributes, variations, and stock status formatted for customer display. **For complex catalog queries** (advanced filtering, search), consider WPGraphQL with WooGraphQL as an alternative that provides more flexible query shapes.

---
[Back to Overview](./OVERVIEW.md)
