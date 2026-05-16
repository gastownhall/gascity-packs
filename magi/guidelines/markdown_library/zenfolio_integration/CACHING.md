# Caching Strategy

Zenfolio gallery content is read-heavy. **A well-designed caching layer reduces API calls by 90%+, improves frontend responsiveness, and reduces the risk of rate limiting.**

### Multi-Layer Architecture

| Layer | Implementation |
|:-----:|:---------------|
| 1 | **Server-side proxy** in-memory cache (Map, Redis, or equivalent) with per-resource TTLs |
| 2 | **React Query** (TanStack Query) cache in the frontend with `staleTime` and `gcTime` configuration |
| 3 | **HTTP cache headers** (`Cache-Control`, `ETag`) on proxy responses to the frontend |

Each layer reduces load on the layer below it.

### Cache TTLs

| Resource | Recommended TTL |
|:---------|:---------------:|
| Gallery metadata (title, caption, photo count) | 5 min |
| Photo list within a gallery | 5 min |
| Individual photo metadata | 10 min |
| Group hierarchy | 15-30 min |
| Popular / recent photos | 15 min |
| Search results | 2 min |
| Category list | 24 hr |
| Auth token | 20 hr |

These values are **starting points** — tune based on observed update frequency and freshness requirements.

### Cache Keys

**Cache keys must be unique per resource and parameter combination.** Key pattern:

```text
zf:{method}:{params_hash}
zf:LoadPhotoSet:f993412712:Level2:true
```

**Include the `IncrementalLevel` and `includePhotos` parameters in the key** — the same gallery loaded at `Level1` and `Level2` returns different data.

### Invalidation on Mutation

When the proxy executes `CreatePhotoSet`, `UpdatePhotoSet`, `DeletePhotoSet`, or any photo mutation:

- Invalidate the affected gallery's cache entry.
- Invalidate its parent group's cache entry.
- Invalidate the group hierarchy cache.

**Use cache tags or prefix-based invalidation** to clear all entries for a specific gallery ID.

### React Query Configuration

| Setting | Recommendation |
|:--------|:---------------|
| `staleTime` | Match the proxy cache TTL (e.g., 5 min for gallery data) |
| `gcTime` (garbage collection) | Longer (30 min) — keeps data available for instant display when navigating back |
| `refetchOnWindowFocus` | `false` for gallery data that does not change frequently |
| `refetchOnMount` | `true` — check for fresh data when a component remounts |

---
[Back to Overview](./OVERVIEW.md)
