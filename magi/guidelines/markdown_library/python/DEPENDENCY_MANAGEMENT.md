# Dependency and Environment Management

### Virtual Environments
- Always use virtual environments. One per project.
- Never install packages globally.
- Activate the venv before development.

### Dependency Files
- Use `requirements.txt` for direct dependencies.
- Never pin versions in `requirements.txt`.
- List direct dependencies only.

### `pyproject.toml` for Metadata
```toml
[project]
name = "package-name"
version = "1.0.0"
description = "Service description"
requires-python = ">=3.14"
dependencies = []
```

### Package Manager
Prefer `uv` over `pip` for speed. Use virtual environments always.

### Dependency Injection
Inject dependencies through the constructor:
```python
class UserService:
    def __init__(self, repository: UserRepository, cache: CacheService) -> None:
        self._repository = repository
        self._cache = cache
```

---
[Back to Overview](./OVERVIEW.md)
