# Performance Optimization

WooCommerce performance determines checkout conversion rate, admin usability, and API response time. Performance optimization spans database queries, caching strategy, and frontend delivery.

### HPOS Performance Win

**Enable HPOS for the single largest performance improvement to order operations.** Stores with 50,000+ orders report **80-90% faster admin order filtering** and **up to 5× faster order creation** after HPOS migration. HPOS eliminates the `wp_postmeta` JOIN overhead that is the primary bottleneck for order queries in the legacy storage.

### Persistent Object Caching

**Implement persistent object caching (Redis, Memcached)** via a WordPress object cache drop-in. WooCommerce's transient-based caching (product lookups, shipping rate calculations, tax rate lookups) benefits significantly from persistent caching. **Without it, transients fall through to the options table**, which performs worse than a dedicated cache backend.

### Page Cache Exclusion

**Exclude cart, checkout, and my-account pages from full-page caching.** These pages contain user-specific, session-dependent content that must not be cached for anonymous visitors and served to authenticated users. Configure cache exclusion rules in Cloudflare, Varnish, or the caching plugin. **WooCommerce sets `DONOTCACHEPAGE` on these pages, but not all cache layers respect it.**

### Action Scheduler Hygiene

**Limit Action Scheduler table growth.** WooCommerce and its extensions (Subscriptions, webhooks, background jobs) use Action Scheduler extensively. Completed and failed actions accumulate in the `wp_actionscheduler_actions` table. Configure retention via the `action_scheduler_retention_period` filter (default 30 days). **Stores processing thousands of actions daily should reduce retention to 7-14 days** and monitor table size.

### Headless Caching Layer

**For headless frontends, implement a caching layer** between the Nuxt/Next.js server and the WooCommerce API. Cache product catalog responses with short TTLs (60-300 seconds). Invalidate cache on product update webhooks. **Cart and checkout endpoints must not be cached** — they are session-specific and mutation-heavy.

---
[Back to Overview](./OVERVIEW.md)
