# Error Handling and Resilience

The Zenfolio API returns errors via **JSON-RPC error objects** (JSON-RPC) or **SOAP faults** (SOAP). Network failures, rate limits, and transient service issues require resilient error handling.

### Error Classification

| Category | Examples | Action |
|:---------|:---------|:-------|
| **Retriable — network** | Connection timeout, DNS resolution failure | Retry with exponential backoff, max 3 attempts, base delay 1s |
| **Retriable — server** | HTTP 500, 502, 503 | Retry with backoff |
| **Retriable — auth** | Token expired | Re-authenticate and retry **once** |
| **Non-retriable** | 400, 404, access denied | **Do not retry** — deterministic failures requiring different handling (re-auth, keyring update, user notification) |

### Exponential Backoff with Jitter

```text
delay = baseDelay * 2^(attempt - 1) + random(0, baseDelay)
```

- Cap maximum delay at 30 seconds.
- **Do not retry indefinitely** — fail after maximum attempts with a descriptive error message.
- **Log every retry attempt** with method name, error type, attempt number, delay.

### Circuit Breaker

Implement a circuit breaker for the Zenfolio API in the server-side proxy:

- After **5 consecutive failures within 60 seconds**, open the circuit.
- Return cached data or a degraded response for **5 minutes** before attempting the next request.

This prevents overwhelming a struggling API and provides predictable degraded behavior during outages.

### User-Facing Error States

Display user-friendly error states in the frontend:

| Condition | Message |
|:----------|:--------|
| 404 on gallery load | "Gallery not found" |
| Access denied | "This gallery is private" |
| Transient error | "Unable to load gallery — please try again" with a retry button |
| Keyring required | "Gallery is password-protected" with a password input |

**Never display raw API error messages, JSON-RPC error codes, or stack traces to end users.**

---
[Back to Overview](./OVERVIEW.md)
