# URL Structure and Naming

### Path Construction

URLs follow a consistent hierarchical pattern:

```
/{version}/{collection}/{resourceId}/{subcollection}/{subresourceId}
```

- Path segments are lowercase
- Use hyphens for multi-word segments: `order-items`, not `orderItems` or `order_items`
- Collection names are plural nouns: `users`, `orders`, `products`
- Resource IDs are opaque strings; clients should not parse or construct them
- Trailing slashes are prohibited; `/users/` and `/users` must resolve identically or the former must redirect

### REST Resource Naming

| Pattern | Format | Correct | Incorrect |
|:--------|:-------|:--------|:----------|
| Collection | `/api/v1/{plural-noun}` | `/api/v1/users` | `/api/v1/user` |
| Singleton | `/api/v1/{plural-noun}/{id}` | `/api/v1/users/123` | `/api/v1/user/123` |
| Sub-resource | `/api/v1/{plural-noun}/{id}/{sub-collection}` | `/api/v1/users/123/orders` | depth > 2 |

### Query Parameters

Query parameters modify the response without changing the resource identity. Names use **camelCase**:

- **Filtering**: `?status=active&createdAfter=2024-01-01`
- **Sorting**: `?sort=createdAt:desc,name:asc`
- **Pagination**: `?limit=20&cursor=abc123`
- **Field Selection**: `?fields=id,name,email`
- **Expansion**: `?expand=orders,profile`

Values are case-sensitive unless domain semantics dictate otherwise.

### URL Anti-Patterns

Avoid these structures:

- Verbs in paths: `/users/create`, `/orders/cancel/{id}`
- File extensions: `/users.json`, `/orders.xml`
- Implementation details: `/api/v1/controllers/userController/getById`
- Redundant segments: `/api/api/v1/users`
- Mixed conventions: `/Users/{userId}/order-items`

### Canonical URLs

Every resource has exactly one canonical URL. Alternative access paths (nested under parent, via search results) return the same representation with the canonical URL in a `self` link. Clients should use canonical URLs for subsequent operations.

---
[Back to Overview](./OVERVIEW.md)
