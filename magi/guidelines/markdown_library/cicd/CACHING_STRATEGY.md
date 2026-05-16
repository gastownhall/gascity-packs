# Caching Strategy

### Cache Dependencies by Lockfile Hash

Cache dependency downloads (`node_modules`, `.pip`, `.m2`, `.cargo`) keyed by the lockfile hash. When the lockfile changes, the cache key changes, and dependencies are freshly downloaded. **Ensures cached dependencies match the declared versions exactly.**

### Cache Docker Layers

Use registry-based caching (`--cache-from`, `--cache-to` with `buildx`) or CI-provided Docker layer caching. Layer caching reduces image build times from minutes to seconds. Ensure cache keys incorporate the Dockerfile hash and build context hash.

### Never Cache Secrets

**Never cache secrets, tokens, credentials, or `.env` files.** Cache entries persist across runs and may be accessible to different branches or contributors depending on the platform's cache isolation model. **Treat the cache as a shared, semi-public storage layer.**

### Cache TTLs and Sizes

Set cache TTLs (prune after 7 days unused) and maximum sizes. Monitor cache hit rates — a cache with low hit rates wastes storage without improving speed.

---
[Back to Overview](./OVERVIEW.md)
