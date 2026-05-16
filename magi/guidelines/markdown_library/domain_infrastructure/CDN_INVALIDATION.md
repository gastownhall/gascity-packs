# CDN Cache Invalidation

### Invalidation Methods

| Method | When to Use |
|:-------|:-----------|
| Deploy-triggered full purge | Simple but aggressive; acceptable for small sites with low traffic. Causes a thundering herd as every edge PoP re-fetches every asset. |
| URL-based purge | Precise but requires knowing exactly which URLs changed. Use when a CMS publishes a single page update. |
| Cache tag purge | Tag responses at origin (`product-123`, `category-shoes`) and purge by tag. Recommended for content-driven sites with complex content/URL relationships. |
| Filename versioning | The best invalidation is no invalidation. Content-hashed filenames are unique per version; old versions expire naturally. Use for all static assets produced by a build pipeline. |

### Invalidation Design Principles

- Prefer versioned URLs over purging. Purging is an operational action that can fail, be delayed, or be applied incorrectly. Versioned URLs are deterministic.
- When purging is necessary, prefer **tag-based** over **URL-based** — tag relationships model content dependencies cleanly.
- Never integrate cache purging into the user request path — purges are asynchronous, eventually consistent operations. Trigger purges via webhooks, event queues, or post-deploy hooks.

Forbidden:

- Cache purging triggered synchronously in the user request path.
- URL-based purging when tag-based purging is available and content relationships are complex.
- Full cache purge for single-item content updates.

---
[Back to Overview](./OVERVIEW.md)
