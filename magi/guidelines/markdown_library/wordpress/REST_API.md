# REST API

### Route Registration

Register custom REST routes via `register_rest_route()` in the `rest_api_init` action. **Organize routes under a vendor namespace** (`acme-analytics/v1`). **Never register under `wp/v2`.** Version the namespace from the start.

**Every route registration includes a `permission_callback`.** Routes without it are publicly accessible. Explicitly return `true` only when the endpoint is intentionally public. **For authenticated endpoints, verify capabilities.**

### Request Validation and Sanitization

Define `validate_callback` and `sanitize_callback` for every route argument. Use **JSON Schema-based arg definitions** (`type`, `format`, `enum`, `minimum`, `maximum`, `required`) for declarative validation. Custom `validate_callback` functions handle complex validation logic. **Validation rejects invalid input before the handler executes. Sanitization cleans valid input before processing.**

### Response Structure

Return `WP_REST_Response` objects with **explicit HTTP status codes**. Use `rest_ensure_response()` to normalize return values. Include pagination headers (`X-WP-Total`, `X-WP-TotalPages`) for collection endpoints. **Error responses use `WP_Error`** with a machine-readable code, human-readable message, and appropriate HTTP status.

### Authentication

WordPress core supports cookie-based authentication (with nonce) and application passwords. **For headless or decoupled frontends** (Nuxt, Next.js), use **application passwords over HTTPS** or integrate JWT with short-lived tokens and refresh rotation. **Never transmit credentials over unencrypted connections.** Rate-limit authentication endpoints.

### REST API Hardening

Restrict the default REST API surface to what is needed. Remove or restrict endpoints exposing sensitive information to unauthenticated requests. Apply rate limiting per route or per consumer. Use `rest_authentication_errors` filter to enforce authentication globally on custom namespaces. **Log failed authentication attempts** with IP, user agent, and targeted route.

---
[Back to Overview](./OVERVIEW.md)
