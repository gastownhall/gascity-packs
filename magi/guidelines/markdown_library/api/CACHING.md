# Caching

### Cache-Control Directives

Set appropriate caching headers for all responses:

```
Cache-Control: public, max-age=3600
Cache-Control: private, no-cache
Cache-Control: no-store
Cache-Control: public, max-age=31536000, immutable
```

| Directive | Meaning |
|:----------|:--------|
| `public` | Response may be cached by any cache |
| `private` | Response is user-specific; only browser caches |
| `max-age` | Seconds the response remains fresh |
| `no-cache` | Must revalidate before using cached copy |
| `no-store` | Never cache; for sensitive data |
| `immutable` | Content never changes (use for hashed asset URLs) |

### ETags

Generate ETags for cacheable resources:

```
ETag: "33a64df551425fcc55e4d42a148795d9f25f89d4"
```

ETag generation strategies:
- Hash of response content
- Resource version number
- Last modification time

Support conditional requests:
- `If-None-Match`: Return 304 Not Modified if ETag matches
- `If-Match`: Return 412 Precondition Failed if ETag doesn't match (optimistic concurrency)

### Cache Invalidation

- Design for cache invalidation from the start; it's harder to add later
- Use versioned URLs or cache keys when content changes
- Support purge mechanisms for CDN caches
- Consider event-driven cache invalidation for real-time requirements

### Vary Header

Indicate which request headers affect response content:

```
Vary: Accept, Authorization
```

Caches store separate entries for different `Vary` header combinations. Over-varying reduces cache efficiency; under-varying serves wrong content.

---
[Back to Overview](./OVERVIEW.md)
