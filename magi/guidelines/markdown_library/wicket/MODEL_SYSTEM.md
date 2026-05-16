# Model System

### Model Types and Selection

| Model | Use |
|:------|:----|
| `Model` | Wraps a static object — only for immutable values |
| `PropertyModel` | Extracts property from target object using expression — updates automatically when target changes |
| `CompoundPropertyModel` | Associates with a container; children inherit model using `wicket:id` as property expression |
| `LoadableDetachableModel` | Loads data on demand and releases on detach — **the workhorse for database-backed data** |
| `LambdaModel` | Functional getter/setter for clean syntax |

**Required selections:**

| Scenario | Model |
|:---------|:------|
| Database entities | `LoadableDetachableModel` with entity ID stored as field. **Never store the entity directly.** |
| Form binding | `CompoundPropertyModel` on the form. Use `PropertyModel` for nested paths or when `CompoundPropertyModel` is insufficient. |
| Computed values | `LoadableDetachableModel` with computation in `load()` method for derived or calculated values. |
| Collections | `LoadableDetachableModel` returning `List` or `Collection` for any collection from database or external service. |

### LoadableDetachableModel Pattern

`LoadableDetachableModel` holds a transient model object set by `load()` when `getObject()` is called. On `detach()`, the object releases. **Store only the identifier as a field** — the entity reloads each request cycle. Provide two constructors: one accepting the ID for detached initialization, one accepting the entity for attached initialization when the object is already available.

**Never capture entity objects in `LoadableDetachableModel` closures or anonymous class fields.** Store only serializable identifiers; load the entity fresh in the `load()` method.

### Common Model Mistakes

- Capturing outer class references in anonymous `LoadableDetachableModel` implementations serializes the entire outer class.
- Using `getModelObject()` in constructors retrieves potentially null or stale data and makes the value static.
- Passing entities directly to components instead of wrapping in models creates serialization bloat and prevents updates.

---
[Back to Overview](./OVERVIEW.md)
