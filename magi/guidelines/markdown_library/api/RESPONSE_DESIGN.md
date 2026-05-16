# Response Design

### Response Structure

Consistent response envelope for all endpoints:

```json
{
  "data": { },
  "meta": {
    "requestId": "abc-123",
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "links": {
    "self": "/users/123"
  }
}
```

For collections:
```json
{
  "data": [ ],
  "meta": {
    "totalCount": 150,
    "pageSize": 20,
    "hasMore": true
  },
  "links": {
    "self": "/users?page=2",
    "next": "/users?page=3",
    "prev": "/users?page=1"
  }
}
```

### Response Headers

Standard headers for all responses:
- `Content-Type`: Media type of response body (with charset, e.g. `application/json; charset=utf-8`)
- `X-Request-ID`: Echo of client's request ID or server-generated if absent
- `ETag`: Entity tag for caching and conditional requests
- `Cache-Control`: Caching directives
- `RateLimit-*`: Rate limiting status (see §12)
- `Vary`: Headers affecting response content

### HATEOAS and Links

Include links to related resources and available actions:

```json
{
  "data": {
    "id": "123",
    "status": "pending"
  },
  "links": {
    "self": "/orders/123",
    "customer": "/customers/456",
    "cancel": "/orders/123/cancel",
    "items": "/orders/123/items"
  }
}
```

Standard link relations:

| Relation | Meaning |
|:---------|:--------|
| `self` | Canonical URL of resource |
| `next` | Next page in collection |
| `prev` | Previous page in collection |
| `first` | First page in collection |
| `last` | Last page in collection |
| `parent` | Parent resource |

For domain actions, use domain-specific relation names: `approve`, `reject`, `cancel`, `archive`. Action links indicate available state transitions.

### Field Selection

Support sparse fieldsets to reduce payload size:

```
GET /users/123?fields=id,name,email
```

Return only requested fields plus always-required fields (id, type). Nested field selection uses dot notation: `?fields=id,name,address.city`.

### Null Handling

- Omit null fields from responses rather than including them explicitly
- Distinguish between "not set" (field absent) and "explicitly null" (field present with null value) only when business semantics require it
- Document null handling behavior in the API specification

---
[Back to Overview](./OVERVIEW.md)
