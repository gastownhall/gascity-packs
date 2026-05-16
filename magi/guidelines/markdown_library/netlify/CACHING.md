# Caching Architecture

### Static Asset Caching

Netlify caches all static assets on global edge nodes. **Cache invalidation happens automatically on every deploy** — atomic deploys ensure visitors never receive a mix of old and new assets.

Do not attempt to set short cache lifetimes on static assets to bust the cache. Setting `Cache-Control: no-cache` on a static HTML file does not make deploys faster; it makes every page load slower by forcing revalidation on content Netlify already invalidates correctly.

### Dynamic Response Caching

Responses from serverless functions, edge functions, and proxy rewrites are not cached by default. Opt into caching by setting cache control headers.

| Header | Scope |
|:-------|:------|
| **`Netlify-CDN-Cache-Control`** | Netlify CDN exclusively; not passed downstream. Use to cache aggressively at CDN without affecting browser behavior |
| `CDN-Cache-Control` | CDN caches generally (Netlify and intermediaries); passed downstream |
| `Cache-Control` | Browser caching; always passed downstream |

When multiple cache control headers are present, Netlify respects the most specific in the order above.

### stale-while-revalidate

```http
Netlify-CDN-Cache-Control: public, s-maxage=300, stale-while-revalidate=60
```

Caches the response for 5 minutes, then serves the stale version for up to 60 additional seconds while revalidating in the background. Eliminates cold-cache latency for dynamic content with acceptable staleness windows.

### Cache Tags

```http
Netlify-Cache-Tag: product-123, catalog-v2
```

Tag cached responses with `Netlify-Cache-Tag` for granular invalidation without full redeploy. Purge by tag via the API or Netlify SDK — propagation across the global network completes in seconds. Use for content that changes on external triggers (CMS publish events, webhook callbacks, database updates) where waiting for a redeploy is unacceptable.

### Cache API

The programmatic Cache API follows the standard `CacheStorage` interface with Netlify-specific extensions. Available in both serverless and edge functions.

```typescript
const cache = await caches.open("my-cache");
const cached = await cache.match(request);
if (cached) return cached;

const response = await fetch("https://api.example.com/data");
await cache.put(request, response.clone());
return response;
```

Caveats:

- Entries are **regionally scoped** — entries written in one region are not replicated.
- Entries invalidate automatically on deploy.
- `keys()` is not implemented.
- Deletions are eventually consistent.

---
[Back to Overview](./OVERVIEW.md)
