# Security Hardening

### Transport Security

- **Require HTTPS for all endpoints**; reject HTTP requests
- TLS 1.2 minimum; prefer TLS 1.3
- Implement HSTS with long `max-age`
- Configure secure cipher suites

### Input Validation

- Validate all input at the boundary before processing
- Reject requests exceeding size limits
- Sanitize input for injection attacks (SQL, NoSQL, command injection)
- Validate `Content-Type` matches expected format
- Implement request schema validation (e.g. against the OpenAPI spec)

### Output Encoding

- Set `Content-Type` with charset: `application/json; charset=utf-8`
- Escape output appropriately for context
- **Never reflect unsanitized input in responses**
- Avoid information leakage in error messages

### Security Headers

Include security headers in all responses:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'none'
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### CORS Configuration

Configure Cross-Origin Resource Sharing precisely:

- Whitelist specific origins; **never use `*` with credentials**
- Limit allowed methods and headers to what's needed
- Set appropriate `Access-Control-Max-Age` for preflight caching
- Validate `Origin` header on the server

### Audit Logging

Log all API access with:
- Timestamp
- Client identifier
- Request method and path
- Response status
- Request ID
- User identity (when authenticated)
- IP address
- Sensitive field access (masked values)

Retain logs according to compliance requirements; enable correlation across services.

---
[Back to Overview](./OVERVIEW.md)
