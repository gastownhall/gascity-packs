# Serialization

### Serialization Fundamentals

Wicket serializes page instances to the page store after each request. Everything reachable from the page must be serializable. Non-serializable fields cause `NotSerializableException` in development, broken back-button navigation, and cluster replication failures.

### Detachable Models

`LoadableDetachableModel` releases its object before serialization. After detach, only the ID field serializes. On next access, `load()` executes again to retrieve fresh data. **This pattern is mandatory for all database-backed data.**

### Transient Fields

Mark non-serializable fields as `transient` and reinitialize on access. With Spring integration, use `@SpringBean` for automatic handling — Spring beans inject as serializable proxies. Without DI, implement lazy initialization pattern checking for null before use.

### Serialization Pitfalls

- Anonymous inner classes capture `this` reference to enclosing class.
- Non-serializable model objects fail silently until page store access.
- Final local variables captured in anonymous classes serialize with the closure.
- **Enable `CheckingObjectOutputStream` in development** to catch violations early.

**Never store database entities or large objects as component fields.** Store only IDs and use `LoadableDetachableModel` to load entities when needed.

---
[Back to Overview](./OVERVIEW.md)
