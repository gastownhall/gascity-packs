# Error Handling and Resilience

### Error Classification

Stripe API errors carry a `type`, `code`, and `message`. Handle by type:

| Type | Cause | Action |
|:-----|:------|:-------|
| `card_error` | Card was declined or failed validation | Display message to customer; **do not retry** |
| `validation_error` | Invalid request parameters | Fix the request; **do not retry** |
| `authentication_error` | API key invalid or expired | Alert operations; **do not retry until corrected** |
| `rate_limit_error` | Too many API requests | Exponential backoff; respect `Retry-After` |
| `api_connection_error` | Network connectivity failure | Retry with exponential backoff and **same idempotency key** |
| `api_error` | Stripe server error (5xx) | Retry with exponential backoff and **same idempotency key**; check Stripe status |
| `idempotency_error` | Idempotency key conflict (reused key with different parameters) | Generate a new key if operation parameters changed |

### Retry Strategy

**Retry only network errors (`api_connection_error`) and server errors (`api_error`) with the same idempotency key.**

- Use exponential backoff: 1s, 2s, 4s, 8s, max 3–5 retries.
- **Do not retry `card_error`, `validation_error`, or `authentication_error`** — deterministic failures that will not resolve on retry.
- The Stripe Node SDK provides built-in retry configuration via `maxNetworkRetries`. Set it to **2–3 for production**. Rely on this built-in mechanism rather than implementing custom retry logic.

### Stripe Status Monitoring

- Monitor `status.stripe.com` for API availability.
- Subscribe to status notifications for the Stripe services your integration depends on (API, Dashboard, Webhooks, Connect).
- Implement a **circuit breaker** for Stripe API calls in high-throughput services: if error rates exceed a threshold, fail fast with a user-friendly message rather than queueing requests that will time out.
- Provide an offline or degraded payment experience (save order for later processing) when Stripe is unavailable if the business model supports it.

---
[Back to Overview](./OVERVIEW.md)
