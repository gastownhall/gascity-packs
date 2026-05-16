# Prohibited Practices

### Never Do

- Use verbs in URL paths; model resources, not actions
- Return 200 OK with error in body; use appropriate status codes
- Include sensitive data in URLs; use headers or request body
- Change response structure without version increment
- Return different structures from the same endpoint based on state
- Use sequential integer IDs exposed externally; they leak information
- Accept credentials in query parameters
- Return stack traces or internal paths in errors
- Mix authentication schemes inconsistently across endpoints
- Break pagination when underlying data changes; use stable cursors
- Return unbounded collections without pagination
- Cache authenticated responses publicly
- Ignore `Content-Type` header on requests
- Return 500 for client errors; distinguish carefully
- Allow HTTP for any endpoint; require HTTPS universally
- Store API keys in client-side code
- Document endpoints that aren't implemented
- Remove fields or endpoints without deprecation period
- Mix custom error envelopes with RFC 7807 in the same API
- Treat health checks or readiness probes as substitutes for shakedown
- Run shakedown against mocked downstreams
- Skip shakedown after a "small" config or middleware change

### Always Do

- Use nouns for resource URLs; HTTP methods indicate action
- Return consistent response envelope structure
- Include request ID in all responses for correlation
- Validate all input at the API boundary
- Validate outgoing responses against the schema in addition to incoming requests
- Document all error codes and conditions
- Implement rate limiting with clear headers
- Version from `v1`; anticipate change
- Use ETags for cacheable resources
- Log all requests with correlation IDs
- Test backward compatibility before release
- Set security headers on all responses
- Validate `Content-Type` matches expected format
- Return 404 for missing resources, not empty 200
- Include pagination links in collection responses
- Require authentication on all endpoints except explicitly public
- Support OPTIONS for CORS preflight
- Monitor error rates and latency percentiles
- Sunset deprecated versions with ample warning (≥ 12 months)
- Support `Idempotency-Key` on mutating endpoints
- Verify webhook signatures and timestamps before processing payloads
- Run shakedown after every trigger condition in §19

---
[Back to Overview](./OVERVIEW.md)
