# Circular Imports

**Resolving circular imports is the highest-priority architectural concern. Correct typing is second.**

### Rules
- Always immediately address circular imports and references when seen.
- Always structure projects to avoid the possibility of circular imports.
- **NEVER use `if TYPE_CHECKING:`** — absolutely prohibited.
- **NEVER import from files outside the same folder as an `__init__.py`.**

### Preferred Resolution Order
1. Extract shared types/models to a dedicated lower-level module (`typings/`).
2. Split a module into `{domain}_models.py` and `{domain}_service.py`.
3. Introduce `Protocol` interfaces and use dependency injection.
4. If forced, use local imports inside functions and document why.
5. **Never use `if TYPE_CHECKING:` as a workaround** — restructure properly.

### Decision Tree
```text
Is the cycle caused by shared types?
├── Yes: Extract types/models to a lower-level module.
└── No: Is the cycle caused by service-to-service calls?
    ├── Yes: Introduce a Protocol and inject dependencies.
    └── No: Split modules by responsibility until imports are one-directional.
```

---
[Back to Overview](./OVERVIEW.md)
