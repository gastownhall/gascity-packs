# Performance Optimization

### Query Optimization

Monitor query count and execution time per page load via Query Monitor (development) or APM tooling (production). **Target under 50 queries per frontend load.** Eliminate N+1 patterns. Cache repeated expensive queries within request lifecycle. **Enable `SAVEQUERIES` only in development.**

### Autoloaded Options

Options with `autoload=yes` load on every request.

| Use case | autoload |
|:---------|:---------|
| Small, frequently-accessed values | `yes` |
| Large serialized arrays or infrequently-accessed data | `no` |

**A plugin storing 500KB with `autoload=yes` adds that to every page's memory baseline.** Audit autoloaded options periodically.

### Page Caching Strategy

Full-page caching is the largest performance lever. **Ensure custom code is cache-compatible.** Avoid setting cookies that bust cache for anonymous users. Fragment caching (transients, object cache) handles dynamic portions. **`admin-ajax.php` and REST routes bypass page cache by default, which is correct.**

---
[Back to Overview](./OVERVIEW.md)
