# Style Summary

| Element | Required Style |
|:--------|:---------------|
| URL Paths | Lowercase with hyphens; plural nouns; no verbs |
| HTTP Methods | GET=read, POST=create, PUT=replace, PATCH=update, DELETE=remove |
| Request Bodies | JSON; camelCase properties; ISO 8601 dates |
| Response Bodies | Consistent envelope with `data`, `meta`, `links` |
| Status Codes | Most specific applicable code; 4xx for client errors, 5xx for server |
| Error Format | Structured with code, message, details, requestId — or RFC 7807 (one or the other, never both) |
| Versioning | URL path prefix `/v1`, `/v2`; integer major versions only |
| Authentication | Bearer token in `Authorization` header; never in URL |
| Pagination | Cursor-based preferred; keyset acceptable; offset only when needed |
| Rate Limits | `RateLimit-*` headers on every response; 429 with `Retry-After` when exceeded |
| Caching | `Cache-Control` and `ETag` headers; support conditional requests |
| Webhooks | HMAC signature + timestamp validation; HTTPS only; exponential-backoff retries |
| GraphQL | Connection-pattern pagination; non-null by default; union-type errors |
| Documentation | OpenAPI 3.1 specification; kept in sync with implementation |
| Security | HTTPS only; validate input; include security headers |
| Field Names | camelCase in JSON; hyphenated in URLs |
| Dates | ISO 8601 with timezone: `2024-01-15T10:30:00Z` |
| IDs | Opaque strings; never sequential integers externally |
| Nulls | Omit null fields; empty arrays instead of null arrays |
| Collections | Always paginated; never unbounded |
| Shakedown | Real downstreams + fixed request corpus + classified outcome (pass / fail-blocking / fail-nonblocking / inconclusive) |
| Defense in Depth | Schema + validation + versioning + rate limits + idempotency + circuit breakers + contract tests + SLO monitoring + shakedown |

---

Following these rules produces APIs that are predictable, evolvable, and maintainable. Clients can integrate with confidence knowing that conventions are consistent and breaking changes are managed. The API becomes a stable foundation that enables rather than constrains the systems built upon it.

**Apply this guidance universally to all HTTP API design across the organization.**

---
[Back to Overview](./OVERVIEW.md)
