# Error Handling

### Domain Exception Hierarchies
Define domain-specific exceptions for meaningful error handling:
```python
class ServiceError(Exception):
    """Base service exception."""


class ValidationError(ServiceError):
    """Input validation failed."""


class NotFoundError(ServiceError):
    """Resource not found."""
```

### Rules
- Catch specific exceptions only — never bare `except:` or broad `except Exception`.
- Never swallow exceptions silently.
- Keep `try` blocks minimal.
- Always re-raise or raise a domain exception — never return a default after catching.
- Preserve context with `from` when re-raising.

### Preserving Context
```python
try:
    config = load_config(path)
except FileNotFoundError as e:
    raise ConfigurationError(f"Not found: {path}") from e
```

### Concise Catch + Re-raise
```python
try:
    connection = connect_to_db("localhost", 5432)
except DatabaseError as e:
    logger.exception("Database connection failed host=localhost port=5432")
    raise
```

### Exception Groups (3.11+)
Handle multiple concurrent failures using `ExceptionGroup`.

### Anti-patterns
- Catching and returning `None` without context.
- Logging without identifiers.
- Wrapping every line in `try/except`.

---
[Back to Overview](./OVERVIEW.md)
