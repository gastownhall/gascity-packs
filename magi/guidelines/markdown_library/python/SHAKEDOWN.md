# Shakedown

### Definition
A shakedown is the first controlled end-to-end execution against real async I/O, real HTTP clients, real database pools, and real settings resolution. It validates the integrated system under real conditions.

### Implementation
- **CLI tools:** a dedicated `shakedown` subcommand.
- **Batch scripts:** a `scripts/shakedown.py` module.
- **Services:** an async `startup_shakedown()` coroutine.

### Mandatory Triggers
- First execution of a new service or CLI.
- Change to async I/O structure or loop ownership.
- Change to HTTP client or DB pool config.
- Change to Pydantic Settings or env var names.
- Dependency upgrade to core libraries.

### Validation Categories
1. **Async I/O flow integrity** — coroutines await, timeouts fire.
2. **HTTP client subsystem** — connects, auths, deserializes into models.
3. **Database pool lifecycle** — round-trips against real DB.
4. **Configuration propagation** — Pydantic Settings resolves env vars.
5. **Exception paths** — context-manager cleanup runs on failure.
6. **Side effects through persistence** — writes land in intended table.

### Principles
- Use representative safe inputs wrapped in Pydantic models.
- Run against sandboxes or isolated stacks.
- Structured logging at DEBUG level.

### Failure Handling
A `FAIL_BLOCKING` result must abort startup:
```python
if result.classification is ShakedownClassification.FAIL_BLOCKING:
    raise RuntimeError("shakedown failed — refusing to accept traffic")
```

### Anti-Patterns
- Implementing shakedown as a pytest suite.
- Mocking core boundaries (httpx, SQLAlchemy) during shakedown.
- Using `dict[str, Any]` for input/output.

---
[Back to Overview](./OVERVIEW.md)
