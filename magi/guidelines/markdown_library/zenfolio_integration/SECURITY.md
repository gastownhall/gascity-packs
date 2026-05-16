# Security

Security in Zenfolio integrations centers on **protecting authentication tokens, preventing credential exposure, enforcing access control, and safeguarding the proxy layer**.

### Token Protection

The Zenfolio authentication token (`X-Zenfolio-Token`) **must never appear in**:

- Client-side JavaScript.
- HTML source.
- Browser network logs accessible to the user.
- Any frontend-delivered asset.

The token lives **exclusively in the server-side proxy's memory or secure storage**. Proxy responses to the frontend do not include the token.

### Credentials in Public Env Vars Forbidden

**Do not embed Zenfolio credentials in environment variables prefixed with `NEXT_PUBLIC_`, `NUXT_PUBLIC_`, `VITE_`, or any mechanism that exposes them to the client bundle.** These are server-only secrets accessed via `runtimeConfig` (Nuxt) or `process.env` (Node.js server) **without public prefixes**.

### Proxy Endpoint Protection

- **Apply rate limiting per client IP.**
- **Validate input parameters** — gallery IDs must be numeric, search queries must be sanitized.
- **Reject requests with malformed IDs** that could cause unexpected API behavior.
- The proxy is a public-facing API surface — **treat it with the same security rigor as any other API endpoint**.

### Strip Upload URLs

**Do not expose `UploadUrl`, `VideoUploadUrl`, or `RawUploadUrl` fields in proxy responses to the frontend.** These URLs, combined with the auth token, enable arbitrary file uploads to the gallery. **Strip these fields in the proxy's response transformation layer.** Upload functionality, if needed, routes through dedicated proxy endpoints with explicit authorization checks.

### Unauthenticated for Public Reads

For public gallery viewing (no authentication required), the Zenfolio API returns public data **without a token**. **Use unauthenticated API calls for public gallery display to minimize token exposure.** Authenticate only when the operation requires it (accessing private galleries, uploading, modifying content). **This reduces the blast radius if the proxy is compromised** — unauthenticated endpoints cannot modify account data.

### CORS

**Restrict proxy CORS to the frontend application's origin.** Block direct cross-origin access to the proxy from unauthorized origins. Prevents third parties from using the proxy as an open Zenfolio API relay.

---
[Back to Overview](./OVERVIEW.md)
