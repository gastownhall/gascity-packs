# HTTP Methods and Semantics

### Method Selection

| Method | Semantics | Idempotent | Safe | Request Body | Response Body |
|:-------|:----------|:-----------|:-----|:-------------|:--------------|
| GET | Retrieve resource | Yes | Yes | No | Yes |
| POST | Create resource or trigger action | No | No | Yes | Yes |
| PUT | Replace resource entirely | Yes | No | Yes | Optional |
| PATCH | Partial update | No* | No | Yes | Yes |
| DELETE | Remove resource | Yes | No | No | Optional |
| HEAD | Retrieve headers only | Yes | Yes | No | No |
| OPTIONS | Retrieve allowed methods | Yes | Yes | No | Yes |

*PATCH can be idempotent depending on patch format; JSON Merge Patch (RFC 7396) is idempotent, JSON Patch (RFC 6902) is not.

### GET

- Retrieves resource representation without side effects
- Response is cacheable by default
- Never modifies server state
- Query parameters filter or modify the representation, not the resource
- Returns 200 with body or 404 if resource doesn't exist

### POST

- Creates a new resource in a collection
- Server assigns the resource identifier
- Returns 201 with `Location` header pointing to new resource
- Response body contains the created resource representation
- Also used for operations that don't fit other methods (complex searches, batch operations)

### PUT

- Replaces the entire resource with the request body
- Client must send the complete resource representation
- Creates the resource if it doesn't exist (when client-specified IDs are allowed)
- Returns 200 with updated resource or 204 with no body
- Omitted fields are set to null or default, not preserved

### PATCH

- Applies partial modifications to a resource
- Request body contains only the fields to update
- Use **JSON Merge Patch (RFC 7396)** for simple updates or **JSON Patch (RFC 6902)** for complex operations
- Returns 200 with updated resource
- Omitted fields are preserved unchanged

### DELETE

- Removes the resource
- Returns 204 with no body on success
- Subsequent GET returns 404
- Deleting a non-existent resource returns 404 or 204 depending on idempotency interpretation
- Consider soft delete for audit requirements; expose via filtered collection, not different endpoint

### Method Override

Some clients cannot send all HTTP methods. Support method override via header when necessary:

```
POST /orders/123 HTTP/1.1
X-HTTP-Method-Override: DELETE
```

Apply override **only to POST requests**. This is a compatibility escape hatch, not a design pattern.

---
[Back to Overview](./OVERVIEW.md)
