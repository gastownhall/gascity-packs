# WC REST API (wc/v3)

The WC REST API provides authenticated access to all WooCommerce resources: orders, products, customers, coupons, shipping, tax, reports, and settings. **It is designed for server-to-server integrations, admin tools, and ERP/CRM synchronization. It is not designed for customer-facing frontend applications.**

### Authentication

Authenticate WC REST API requests with consumer key/secret pairs generated in WooCommerce > Settings > Advanced > REST API.

| Requirement | Detail |
|:------------|:-------|
| Transport | **HTTPS exclusively** — secrets transmitted over HTTP are compromised immediately |
| Auth | HTTP Basic auth: consumer key as username, secret as password |
| Embedding | **Never** embed consumer keys in client-side JavaScript, mobile app bundles, or public repositories |

### Permission Scoping

Scope API key permissions to the minimum required:

| Use case | Permission |
|:---------|:-----------|
| Reporting integration | Read-only |
| Order management | Write |
| Full ERP sync | Read/write |

**Separate keys per integration** enable independent rotation and revocation.

### Versioning, Pagination, Rate Limiting

- **Pin the API version** in all client code. Use `wc/v3` explicitly in endpoint URLs. Do not rely on version-less endpoints. Pinning prevents unexpected breakage when WooCommerce adds a new API version.
- **Paginate list endpoints**. Default `per_page` is 10; max is 100. Use `X-WP-Total` and `X-WP-TotalPages` response headers for pagination metadata. **Never fetch all records in a single request** — use the `modified_after` parameter for incremental sync.
- **Respect rate limits**. WooCommerce itself does not enforce API rate limits, but hosting providers, CDNs, and WordPress security plugins may. Implement client-side rate limiting (e.g., 5 req/s) and exponential backoff on 429 or 5xx. **Use batch operations** (`batch` endpoint) to reduce request count.

---
[Back to Overview](./OVERVIEW.md)
