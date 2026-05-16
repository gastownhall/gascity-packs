# CDN Architecture and Caching

### CDN Fundamentals

A CDN caches content at edge servers geographically distributed near users. Cache hits serve instantly from the edge; cache misses fetch from the origin, cache the response, and serve it. The cache hit ratio directly determines origin load, bandwidth cost, and user-perceived latency. A well-tuned CDN achieves 90%+ cache hit ratio for static-heavy sites.

### Cache-Control Headers

Cache behavior is controlled by HTTP response headers from the origin. The CDN reads these headers and acts accordingly.

| Header | Use Case |
|:-------|:---------|
| `Cache-Control: public, max-age=31536000, immutable` | One-year cache; content never changes at this URL. Use for fingerprinted/hashed static assets. |
| `Cache-Control: public, max-age=0, must-revalidate` | Check with origin on every request but serve 304 Not Modified if content has not changed. Use for HTML pages that change with any deploy. |
| `Cache-Control: no-store` | Never cache. Use for authenticated API responses, user-specific content, pages with sensitive data. |
| `Cache-Control: public, max-age=60, stale-while-revalidate=300` | Cache for 60s then serve stale for up to 300 additional seconds while refreshing. Use for semi-dynamic content where slight staleness is acceptable. |

### Cache Key Design

The cache key determines whether two requests are considered identical by the CDN. By default, the full URL (scheme + host + path + query string) forms the cache key. Irrelevant query parameters fragment the cache — the same content is cached multiple times under different keys, destroying hit ratio.

Required:

- Strip or ignore tracking query parameters: `utm_source`, `utm_medium`, `utm_campaign`, `fbclid`, `gclid`.
- Sort query parameters so `?a=1&b=2` and `?b=2&a=1` share a cache entry.
- Exclude the `Cookie` header from the cache key unless content genuinely varies per user.

Forbidden:

- `Vary: Cookie` on cacheable resources — creates a unique cache entry per user, reducing hit ratio to near zero.

### Origin Shielding

Origin shielding (tiered caching) adds a middle cache layer between edge PoPs and the origin. Without shielding, every edge PoP independently fetches from the origin on cache miss. With shielding, edge PoPs fetch from a single designated shield PoP, which consolidates requests to the origin. This dramatically reduces origin load during cache misses and traffic spikes.

Cloudflare provides tiered caching automatically on paid plans. For origins in specific regions, ensure the shield PoP is geographically close to the origin to minimize fetch latency.

### Content-Type Caching

| Content Type | Strategy |
|:-------------|:---------|
| Immutable assets (hashed JS, CSS, images, fonts) | `max-age=31536000, immutable` — never invalidate; filename changes when content changes |
| HTML pages | `max-age=0, must-revalidate` or short max-age with `stale-while-revalidate` — HTML is the entry point and must reference current asset versions |
| API responses | Case-by-case — public read-heavy responses benefit from short TTLs with SWR; authenticated/user-specific must not be cached at the CDN |
| Media (video, audio, large downloads) | Long TTLs — content changes infrequently and cache misses are expensive due to file size |

---
[Back to Overview](./OVERVIEW.md)
