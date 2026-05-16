# Error Handling

### Standard Error Response Format

All error responses follow a consistent structure:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "\nThe request contains invalid data",
    "details": [
      {
        "field": "email",
        "code": "INVALID_FORMAT",
        "message": "\nEmail address is not valid"
      },
      {
        "field": "age",
        "code": "OUT_OF_RANGE",
        "message": "\nAge must be between 18 and 120"
      }
    ],
    "requestId": "abc-123",
    "timestamp": "2024-01-15T10:30:00Z",
    "documentationUrl": "https://api.example.com/docs/errors/VALIDATION_FAILED"
  }
}
```

### RFC 7807 Problem Details (Alternative)

For APIs aligning with the IETF standard, use **RFC 7807 Problem Details for HTTP APIs** instead. Required fields: `type`, `title`, `status`. Optional: `detail`, `instance`. Custom fields are permitted as siblings:

```json
{
  "type": "https://example.com/probs/out-of-credit",
  "title": "You do not have enough credit.",
  "status": 403,
  "detail": "Your current balance is 30, but that costs 50.",
  "instance": "/account/12345/msgs/abc",
  "balance": 30,
  "accounts": ["/account/12345", "/account/67890"]
}
```

Pick one format per API and apply consistently. Mixing custom envelopes and RFC 7807 within the same API is forbidden.

### Error Code Design

- Use stable, machine-readable error codes that clients can program against
- Error codes are **SCREAMING_SNAKE_CASE** strings
- Codes are hierarchical when useful: `AUTH_EXPIRED`, `AUTH_INVALID`, `AUTH_MISSING`
- **Never change error codes once published**; add new codes for new conditions
- Messages are human-readable and may change; codes are for programmatic handling

### Error Categories

Categorize errors to help clients handle them appropriately:

- **Retryable**: Transient failures that may succeed on retry (503, 429, some 500s)
- **Client-Fixable**: Invalid input the client can correct and retry (400, 422)
- **Terminal**: Permanent failures requiring human intervention (403, 404, 409)

Include retry hints for retryable errors:
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "retryable": true,
    "retryAfter": 30
  }
}
```

### Internal Error Handling

- **Never expose stack traces, internal paths, or implementation details** in error responses
- Log full error context server-side with request ID for correlation
- Return generic 500 response for unexpected errors; specific codes for known failure modes
- Include request ID in every error response to enable support correlation

---
[Back to Overview](./OVERVIEW.md)
