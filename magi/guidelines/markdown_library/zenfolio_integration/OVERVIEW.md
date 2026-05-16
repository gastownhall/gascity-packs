# Zenfolio API Integration Library

**Runtime:** Zenfolio API v1.8 (current, only supported version), JSON-RPC over HTTPS, SOAP over HTTPS (legacy), React 18+ / Nuxt 3+ for frontend integrations, TanStack Query (React Query) for data fetching.

Defines strict conventions for building against the Zenfolio API directly. Covers API protocol selection, authentication token lifecycle, keyring management for password-protected galleries, data model navigation (PhotoSets, Groups, Photos), image URL construction and sizing, access control enforcement, upload and mutation workflows, caching strategy, rate limiting, error handling, headless frontend integration patterns (React/Nuxt), e-commerce cart integration, and operational security for API credentials and token exposure prevention.

Applies to all applications, services, and frontend clients that interact with the Zenfolio API programmatically — custom gallery viewers, photo browsing applications, e-commerce integrations, automated upload pipelines, synchronization utilities, mobile applications, headless storefronts.

## Critical Mandates (Read First)

- **Zenfolio Is the Source of Truth** — When local state conflicts with Zenfolio's API response, Zenfolio wins.
- **Server-Side Proxy for All Mutating Operations** — Authentication tokens grant full account access and must never reach client-side code.
- **Respect the Hierarchy** — User → Root Group → Groups → PhotoSets → Photos.
- **Cache Aggressively, Invalidate Precisely** — Stale data for hours indicates a broken invalidation strategy.
- **Graceful Degradation** — Never present a blank page because a single API call failed.
- **Single endpoint, HTTPS only** — All API requests target `https://api.zenfolio.com/api/1.8/zfapi.asmx`; HTTP is prohibited.
- **User-Agent identification mandatory** — Never impersonate a web browser.
- **Shakedown Required** — Validation against a known-good test gallery on a real Zenfolio account before enabling production processing on every triggering change.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [API Protocol and Request Format](./PROTOCOL.md)
3. [Authentication and Token Management](./AUTHENTICATION.md)
4. [Keyring and Password-Protected Gallery Access](./KEYRING.md)
5. [Data Model and Object Hierarchy](./DATA_MODEL.md)
6. [Image URL Construction and Sizing](./IMAGE_URLS.md)
7. [Access Control](./ACCESS_CONTROL.md)
8. [Photo and Gallery Mutations](./MUTATIONS.md)
9. [Search and Discovery](./SEARCH.md)
10. [Caching Strategy](./CACHING.md)
11. [Error Handling and Resilience](./ERROR_HANDLING.md)
12. [Headless Frontend Integration](./HEADLESS.md)
13. [E-Commerce and Cart Integration](./ECOMMERCE.md)
14. [Rate Limiting and API Usage](./RATE_LIMITING.md)
15. [Security](./SECURITY.md)
16. [Performance Optimization](./PERFORMANCE.md)
17. [Monitoring and Observability](./MONITORING.md)
18. [Testing](./TESTING.md)
19. [Shakedown — Integration Validation](./SHAKEDOWN.md)
20. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
21. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
22. [Required Practices](./REQUIRED_PRACTICES.md)
23. [Style Summary](./STYLE_SUMMARY.md)
