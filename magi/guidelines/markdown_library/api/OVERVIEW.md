# API Design Guidelines Library

This directory contains an expanded, modularized version of the API Design Guidelines. These guidelines are mandatory for all HTTP API design across the organization, optimizing for predictability, discoverability, evolvability, debuggability, and performance by default.

## Critical Mandates (Read First)
- **The API Is a Contract** — Every endpoint, field, and behavior is a permanent commitment.
- **Resources Over Actions** — URLs identify resources (nouns); HTTP methods identify operations (verbs).
- **Schema-First** — OpenAPI/GraphQL schema is the source of truth for both producer and consumer.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Predictability, discoverability, evolvability, debuggability, performance; API style selection.
2. [Resource Modeling](./RESOURCE_MODELING.md) — Identification, granularity, relationships, singleton vs collection, state.
3. [URL Structure and Naming](./URL_STRUCTURE_NAMING.md) — Path construction, query parameters, anti-patterns, canonical URLs.
4. [HTTP Methods and Semantics](./HTTP_METHODS_SEMANTICS.md) — GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS, method override.
5. [Request Design](./REQUEST_DESIGN.md) — Content negotiation, headers, body structure, validation, idempotency keys.
6. [Response Design](./RESPONSE_DESIGN.md) — Response structure, headers, HATEOAS, field selection, null handling.
7. [Status Codes](./STATUS_CODES.md) — Success, client error, and server error codes with decision tree.
8. [Error Handling](./ERROR_HANDLING.md) — Standard format, RFC 7807 alternative, error codes, categories, internal handling.
9. [Versioning Strategy](./VERSIONING_STRATEGY.md) — Placement, numbering, breaking vs non-breaking, deprecation process.
10. [Authentication and Authorization](./AUTH.md) — Methods, token transmission, RBAC/ABAC, security response codes.
11. [Pagination and Filtering](./PAGINATION_FILTERING.md) — Cursor, keyset, offset, filtering, sorting, response metadata.
12. [Rate Limiting and Throttling](./RATE_LIMITING.md) — Design, headers, exceeded response, throttling strategies.
13. [Caching](./CACHING.md) — Cache-Control directives, ETags, invalidation, Vary header.
14. [Webhooks](./WEBHOOKS.md) — Payload schema, security, reliability, registration endpoints.
15. [GraphQL Schema Design](./GRAPHQL_SCHEMA.md) — Schema organization, naming, nullability, connection pagination, errors.
16. [Security Hardening](./SECURITY_HARDENING.md) — Transport, input validation, output encoding, CORS, audit logging.
17. [Documentation Standards (OpenAPI 3.1)](./DOCUMENTATION_OPENAPI.md) — Specification, completeness, examples, interactive docs.
18. [Testing and Validation](./TESTING_VALIDATION.md) — Contract testing, categories, coverage, load metrics, pre-release.
19. [Shakedown](./SHAKEDOWN.md) — Definition, surfaces, triggers, execution, classification, anti-patterns.
20. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
21. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do / Always Do lists.
22. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
