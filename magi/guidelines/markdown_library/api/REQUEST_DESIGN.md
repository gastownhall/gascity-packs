# Request Design

### Content Negotiation

Clients specify acceptable response formats via `Accept` header:
```
Accept: application/json
Accept: application/json, application/xml;q=0.9
```

APIs should support JSON as the primary format. Additional formats (XML, CSV) are optional based on client requirements. Return 406 Not Acceptable if the requested format is unsupported.

### Request Headers

Standard headers for all requests:
- `Content-Type`: Media type of request body (required when body present)
- `Accept`: Acceptable response media types
- `Authorization`: Authentication credentials
- `X-Request-ID`: Client-generated correlation identifier (optional but recommended)
- `If-None-Match`: Conditional GET with ETag
- `If-Match`: Conditional update with ETag for optimistic concurrency
- `Idempotency-Key`: Retry-safe operation identifier (see Idempotency Keys)

### Request Body Structure

JSON request bodies follow consistent conventions:

- Property names use **camelCase**
- Dates use **ISO 8601 with timezone**: `2024-01-15T10:30:00Z`
- Monetary values include currency: `{ "amount": 99.99, "currency": "USD" }`
- Enumerations use SCREAMING_SNAKE_CASE or lowercase strings; document the choice
- **Null values are omitted** rather than explicitly included
- **Arrays are never null**; use empty array for absence

### Validation

Validate request bodies strictly:
- Reject unknown properties (configurable for forward compatibility)
- Enforce type constraints at the boundary
- Validate business rules before processing
- Return all validation errors in a single response, not one at a time

### Idempotency Keys

For non-idempotent operations where retry safety matters, support idempotency keys:

```
POST /payments HTTP/1.1
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

Store the key with the result; return the stored result on duplicate requests. Keys expire after a reasonable window (24-48 hours).

---
[Back to Overview](./OVERVIEW.md)
