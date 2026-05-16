# Cart and Session Handling for Headless Frontends

WooCommerce's cart is session-based. In traditional (monolithic) mode, sessions use cookies set by the WooCommerce PHP session handler. **In headless mode, the frontend runs on a different origin, which means WooCommerce cookies do not propagate.** The `Cart-Token` mechanism bridges this gap.

### Cart-Token Session Management

For headless frontends (Nuxt, Next.js, React), use the `Cart-Token` header for session management:

1. On the **first request** to `/wc/store/v1/cart` (GET), the response includes a `Cart-Token` header containing a JWT that identifies the cart session.
2. **Store this token client-side** (in-memory variable or cookie on the frontend domain).
3. **Include it as a `Cart-Token` request header** on all subsequent Store API requests.

This replaces cookie-based session tracking.

### Nonce vs Cart-Token

**When using `Cart-Token`, the `Nonce` header is not required.** Nonces are tied to the WordPress cookie session and are irrelevant in a headless context where the WordPress session cookie does not exist. Sending a stale or invalid `Nonce` alongside a valid `Cart-Token` causes request failures. **Choose one mechanism:**

| Mechanism | Use |
|:----------|:----|
| `Cart-Token` | Headless |
| `Nonce` | Traditional |

### No Mixed Checkout Modes

**Do not mix traditional WooCommerce shortcode-based checkout with headless Store API checkout on the same WooCommerce installation without explicit session isolation.** The traditional cart and the Store API cart operate on the same underlying `WC_Session_Handler`. A customer who adds items via the Store API and then visits the shortcode-based cart page may see those items, **but session state can conflict** — especially around coupons, shipping selections, and customer address data.

### Authenticated Cart Merging

For authenticated users in headless mode, cart merging (combining a guest cart with a logged-in user's persistent cart) requires the WordPress backend to recognize the user's identity. **The Store API does not natively handle JWT-based user authentication for cart merging.** Solutions:

- Authenticate the user via WordPress application passwords or a JWT plugin.
- Set the current user server-side via custom middleware.
- Manage guest-to-authenticated cart migration via custom server-side logic triggered on login.

### Token Persistence and Expiration

- **Persist the `Cart-Token` across page reloads and navigation** in the Nuxt/SPA frontend. Loss of the `Cart-Token` means loss of the cart session — the user's cart appears empty. Store the token in a cookie on the frontend domain (`httpOnly` if set via a BFF, or accessible if set via client JS) or in a Pinia store backed by cookie persistence for SSR compatibility.
- **Handle cart expiration gracefully.** WooCommerce sessions expire after 48 hours of inactivity by default (configurable via `wc_session_expiring` and `wc_session_expiration` filters). When a `Cart-Token` references an expired session, the Store API returns a fresh empty cart. **The frontend must detect this condition** (cart items suddenly empty after a valid token was sent) and either prompt the user or silently re-initialize.

### CORS Configuration

- **Configure CORS headers** on the WordPress/WooCommerce backend to allow requests from the headless frontend origin.
- **Allow `Cart-Token` and `Nonce` headers** in `Access-Control-Allow-Headers`.
- **Expose the `Cart-Token` header** in `Access-Control-Expose-Headers` so the frontend JavaScript can read it from response headers. **Without CORS exposure, browsers silently strip the `Cart-Token` from the response, making headless cart management impossible.**
- **Never use `Access-Control-Allow-Origin: *`** for the WooCommerce REST API in production. Whitelist the specific frontend origin(s). Wildcard CORS on endpoints that accept authentication headers or modify state is a security vulnerability.

---
[Back to Overview](./OVERVIEW.md)
