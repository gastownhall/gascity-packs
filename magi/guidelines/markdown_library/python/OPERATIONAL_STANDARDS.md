# Operational Standards

Production failures are usually boundary failures: timeouts, retries, bad inputs, missing config, partial outages.

### Timeouts
- Any I/O uses explicit timeouts.
- Defaults live in typed config and are passed into clients.

### Retries
- Retry only idempotent operations.
- Bound retries. Use backoff.
- Stop retrying on deterministic failures (validation, auth).

### Resource Ownership
- If code opens a file/connection/client, code closes it.
- Context managers are preferred for enforcing cleanup semantics.

### Secrets Handling
- Never log secrets.
- Never embed secrets in source.
- Treat environment variables as untrusted input until validated into typed config.
- Use `repr=False` on sensitive Pydantic fields.

---
[Back to Overview](./OVERVIEW.md)
