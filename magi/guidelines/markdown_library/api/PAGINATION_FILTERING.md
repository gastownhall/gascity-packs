# Pagination and Filtering

### Cursor-Based Pagination (Preferred)

Prefer cursor-based pagination over offset-based:

```
GET /users?limit=20
Response includes: "nextCursor": "abc123"

GET /users?limit=20&cursor=abc123
```

Cursors are opaque tokens encoding position. Benefits:
- Stable across concurrent modifications
- Efficient for large datasets (no offset scan)
- Prevents page drift when items are added/removed

### Keyset Pagination

Alternative stable pagination using indexed columns when cursor opacity is undesirable (e.g. when the client wants to know which row it's at):

```
GET /users?limit=20&afterId=123
```

### Offset-Based Pagination

Use only when clients require random page access or total count is necessary:

```
GET /users?limit=20&offset=40
```

Include total count in metadata for UI pagination controls. Be aware that offset pagination degrades at scale and produces inconsistent results during modifications.

### Filtering

Support filtering via query parameters:

```
GET /orders?status=pending&customerId=123&createdAfter=2024-01-01
```

- Simple equality: `?status=pending`
- Multiple values (OR): `?status=pending,processing`
- Comparisons: `?createdAfter=2024-01-01`, `?amountGte=100`
- Nested fields: `?customer.country=US`

Complex filters may require a query DSL or POST with filter body for advanced use cases.

### Sorting

Specify sort order via query parameter:

```
GET /orders?sort=createdAt:desc,status:asc
```

- Default sort order should be deterministic (include ID as tiebreaker)
- Document available sort fields; reject unknown fields
- Limit sortable fields to indexed columns for performance

### Response Metadata

Include pagination context in response:

```json
{
  "meta": {
    "totalCount": 1523,
    "pageSize": 20,
    "hasMore": true
  },
  "links": {
    "self": "/orders?cursor=abc",
    "next": "/orders?cursor=def",
    "prev": "/orders?cursor=xyz"
  }
}
```

`totalCount` is optional — computing it can be expensive at scale. `hasMore` is required.

---
[Back to Overview](./OVERVIEW.md)
