# Core Principles

### Zenfolio Is the Source of Truth

Zenfolio owns the canonical state for **all gallery structures, photo metadata, access control settings, and image assets**. Local databases, caches, and frontend state store references and snapshots for performance. **When local state conflicts with Zenfolio's API response, Zenfolio wins.** Synchronization flows detect and correct drift — they do not override Zenfolio.

### Server-Side Proxy for All Mutating Operations

The Zenfolio API uses authentication tokens that grant **full account access**. **These tokens must never reach client-side code.** All authenticated API calls (uploads, updates, deletions, access control changes) route through a server-side proxy (Nitro server route, Express API, serverless function) that holds the authentication token. **The client sends requests to the proxy; the proxy calls Zenfolio.** Public read-only operations may call Zenfolio directly from the client when no authentication is required, but even these benefit from a proxy for caching, rate limiting, and response transformation.

### Respect the Hierarchy

Zenfolio organizes content in a strict hierarchy:

```text
User → Root Group → Groups (nested) → PhotoSets (Galleries and Collections) → Photos
```

- **Groups** contain PhotoSets and other Groups.
- **Galleries** physically contain photos.
- **Collections** contain links to photos that live in galleries.

**Navigation, caching, and access control all follow this tree structure.** Understanding the hierarchy is prerequisite to building any Zenfolio integration.

### Cache Aggressively, Invalidate Precisely

Zenfolio gallery content changes infrequently relative to read frequency. A sports photography gallery may be updated once per event but viewed thousands of times. **Cache API responses at the proxy layer with TTLs calibrated to the content's change frequency.** Invalidate specific cache entries on known mutation events rather than flushing the entire cache. **Stale data is tolerable for seconds to minutes; stale data for hours indicates a broken invalidation strategy.**

### Graceful Degradation

The Zenfolio API is a third-party dependency. Network failures, rate limits, maintenance windows, and API changes are outside your control. The application must handle API unavailability gracefully:

- Serve cached data when available.
- Display meaningful error states.
- Retry transient failures with exponential backoff.
- **Never present a blank page because a single API call failed.**

### Hard Rules (Core)

- **Single endpoint, HTTPS only** — All API requests target `https://api.zenfolio.com/api/1.8/zfapi.asmx` over HTTPS. **No other endpoint or API version is supported. HTTP (non-TLS) requests are prohibited.**
- **User-Agent identification mandatory** — Every API request includes a User-Agent identification string via the `X-Zenfolio-User-Agent` header or the standard `User-Agent` header. The string identifies application name, version, and URL. **Never impersonate a web browser.** Zenfolio may block requests with generic or missing user agent strings.

---
[Back to Overview](./OVERVIEW.md)
