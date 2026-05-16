# Generics and Type Constraints

### Constraint Ordering

Apply constraints in order: `class`/`struct`/`notnull`, base class, interfaces, `new()`:

```csharp
public sealed class Repository<TEntity> where TEntity : class, IEntity, new() { }
public interface IHandler<TRequest, TResponse> where TRequest : notnull where TResponse : notnull { }
```

### Variance Annotations

Use covariance (`out`) for types that only produce values; contravariance (`in`) for types that only consume:

```csharp
public interface IReadRepository<out TEntity> where TEntity : class {
    Task<TEntity?> FindAsync(Guid id, CancellationToken ct);
    Task<IReadOnlyList<TEntity>> GetAllAsync(CancellationToken ct);
}

public interface IEventHandler<in TEvent> where TEvent : IEvent {
    Task HandleAsync(TEvent @event, CancellationToken ct);
}
```

### Generic Method Design

Prefer explicit generic arguments when inference fails or is ambiguous. **Methods with more than three type parameters indicate design problems.**

### Static Abstract Interface Members

```csharp
public interface IIdentifiable<TSelf> where TSelf : IIdentifiable<TSelf> {
    static abstract TSelf Create(Guid id);
    Guid Id { get; }
}

public sealed record UserId(Guid Id) : IIdentifiable<UserId> {
    public static UserId Create(Guid id) => new(id);
}
```

---
[Back to Overview](./OVERVIEW.md)
