# Migration to Containers

### Containerization Readiness Assessment

Before containerizing an application, verify:

- Logs written to stdout/stderr.
- Configuration via environment variables.
- No hardcoded paths or hostnames.
- Graceful shutdown handling.
- Health check endpoints available.
- State externalized (database, object storage, cache).
- Secrets not embedded in source.
- Fast startup (under 30s).

If any item fails, fix the application before containerizing.

### Strangler Fig Pattern

For monolith-to-microservice migration:

1. Identify extraction candidates (bounded contexts with clear interfaces).
2. Create a facade or proxy layer.
3. Extract and containerize the component.
4. Route traffic from monolith to new component.
5. Remove the extracted code from the monolith.

Iterate until the monolith is decomposed.

---
[Back to Overview](./OVERVIEW.md)
