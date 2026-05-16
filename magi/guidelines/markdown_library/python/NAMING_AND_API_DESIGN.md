# Naming and API Design

- **Functions are verbs:** `load_config`, `parse_request`, `build_report`.
- **Data objects are nouns:** `UserRecord`, `DeployPlan`, `RetryPolicy`.
- **Booleans read as predicates:** `is_enabled`, `has_access`, `should_retry`.
- **Avoid generic sink names:** `data`, `info`, `payload` — unless the domain truly is unknown.

### Public API Requirements
Any function or class considered public (imported from a module, used by other modules, part of a library surface) must:
- Have type hints on all parameters and return values.
- Use Pydantic models for structured inputs and outputs.
- Avoid optional positional arguments that change meaning based on position.

### Function vs Method vs Class
- Use a **function** when behavior is stateless and operates on explicit inputs.
- Use a **class** when:
  - You need encapsulated state, or
  - You need a stable dependency bundle (clients, caches, config), or
  - You need polymorphism (via `Protocol` or base classes), or
  - You are modeling a lifecycle (open/close, start/stop).

---
[Back to Overview](./OVERVIEW.md)
