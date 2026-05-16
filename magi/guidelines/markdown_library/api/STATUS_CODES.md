# Status Codes

### Success Codes

| Code | Meaning | Usage |
|:-----|:--------|:------|
| 200 | OK | Successful GET, PUT, PATCH with response body |
| 201 | Created | Successful POST creating a resource |
| 202 | Accepted | Request accepted for async processing |
| 204 | No Content | Successful DELETE or PUT with no response body |

### Client Error Codes

| Code | Meaning | Usage |
|:-----|:--------|:------|
| 400 | Bad Request | Malformed request syntax, invalid JSON |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Valid authentication but insufficient permissions |
| 404 | Not Found | Resource does not exist |
| 405 | Method Not Allowed | HTTP method not supported for this resource |
| 406 | Not Acceptable | Requested format not supported |
| 409 | Conflict | Request conflicts with current state |
| 410 | Gone | Resource existed but has been deleted |
| 412 | Precondition Failed | Conditional request precondition not met |
| 415 | Unsupported Media Type | Request `Content-Type` not supported |
| 422 | Unprocessable Entity | Request body fails validation |
| 429 | Too Many Requests | Rate limit exceeded |

### Server Error Codes

| Code | Meaning | Usage |
|:-----|:--------|:------|
| 500 | Internal Server Error | Unexpected server failure |
| 502 | Bad Gateway | Upstream service failure |
| 503 | Service Unavailable | Temporary overload or maintenance |
| 504 | Gateway Timeout | Upstream service timeout |

### Status Code Decision Tree

```text
Request successful?
├── Resource created          → 201 Created
├── Async processing accepted → 202 Accepted
├── No response body          → 204 No Content
└── default                   → 200 OK

Client error?
├── Malformed syntax        → 400 Bad Request
├── Missing authentication  → 401 Unauthorized
├── Insufficient perms      → 403 Forbidden
├── Resource not found      → 404 Not Found
├── Method not supported    → 405 Method Not Allowed
├── Format not acceptable   → 406 Not Acceptable
├── State conflict          → 409 Conflict
├── Precondition failed     → 412 Precondition Failed
├── Validation failed       → 422 Unprocessable Entity
└── Rate limit exceeded     → 429 Too Many Requests

Server error?
├── Upstream failure  → 502 Bad Gateway
├── Service unavail.  → 503 Service Unavailable
├── Upstream timeout  → 504 Gateway Timeout
└── default           → 500 Internal Server Error
```

### Status Code Selection

Choose the most specific applicable code. When uncertain:
- **Validation failures** → 422 (not 400)
- **Business rule violations** → 409 or 422 depending on whether it's a state conflict or input issue
- **Authorization failures** → 403 (not 401, unless authentication is actually missing)
- **Missing resources** → 404 (not 400)

---
[Back to Overview](./OVERVIEW.md)
