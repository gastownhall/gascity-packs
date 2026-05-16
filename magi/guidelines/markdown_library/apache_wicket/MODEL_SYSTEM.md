# Model System

### Model Types and Selection

| Model | Use case |
|:------|:---------|
| `Model<T>` | Wraps a static object — only for immutable values |
| `PropertyModel<T>` | Extracts property from target object via expression — updates automatically when target changes |
| `CompoundPropertyModel<T>` | Associates with a container; children inherit model using `wicket:id` as property expression |
| `LoadableDetachableModel<T>` | Loads data on demand and releases on detach — the workhorse for database-backed data |
| `LambdaModel<T>` | Functional getter/setter for clean syntax |

Selection rules:
- **Database entities** — Always use `LoadableDetachableModel` with the entity ID stored as a field. Never store the entity directly.
- **Form binding** — Use `CompoundPropertyModel` on the form. Use `PropertyModel` for nested paths or when `CompoundPropertyModel` is insufficient.
- **Computed values** — Use `LoadableDetachableModel` with computation in `load()` for derived or calculated values.
- **Collections** — Use `LoadableDetachableModel` returning `List` or `Collection` for any collection from database or external service.

### LoadableDetachableModel Pattern

`LoadableDetachableModel` holds a transient model object set by `load()` when `getObject()` is called. On `detach()`, the object releases. Store only the identifier as a field — the entity reloads each request cycle. Provide two constructors: one accepting the ID for detached initialization, one accepting the entity for attached initialization when the object is already available:

```java
public class OrderModel extends LoadableDetachableModel<Order> {

    @SpringBean
    private OrderService orderService;

    private final Long orderId;

    public OrderModel(Long orderId) {
        this.orderId = orderId;
        Injector.get().inject(this);
    }

    public OrderModel(Order order) {
        super(order);
        this.orderId = order.getId();
        Injector.get().inject(this);
    }

    @Override
    protected Order load() {
        return orderService.findById(orderId);
    }
}
```

**Never capture entity objects in `LoadableDetachableModel` closures or anonymous-class fields.** Store only serializable identifiers; load the entity fresh in `load()`.

### Common Model Mistakes

- **Capturing outer-class references** in anonymous `LoadableDetachableModel` implementations serializes the entire outer class.
- **Calling `getModelObject()` in constructors** retrieves potentially null or stale data and freezes the value statically. Read models in `onInitialize`/`onConfigure`/`onBeforeRender`, not the constructor.
- **Passing entities directly to components** instead of wrapping in models creates serialization bloat and prevents updates.

---
[Back to Overview](./OVERVIEW.md)
