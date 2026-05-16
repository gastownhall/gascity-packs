# Records, Structs, and Value Types

### Record Selection Criteria

Use `record` for immutable data transfer objects, events, and value objects with value equality:

```csharp
public sealed record OrderCreatedEvent(Guid OrderId, string CustomerId, DateTimeOffset CreatedAt);
public sealed record Money(decimal Amount, string Currency);
public sealed record Address(string Street, string City, string PostalCode, string Country);
```

Records provide synthesized equality, `ToString()`, and non-destructive mutation via `with` expressions.

### Decision Tree

| Condition | Use |
|:----------|:----|
| Is DTO | record |
| Is event | record |
| Is value object | record |
| Needs value equality | record |
| Size under 16 bytes | record struct |
| Needs inheritance | class |
| Needs mutable state (with justification) | class |

### Record Struct for Performance-Critical Value Types

```csharp
public readonly record struct Coordinate(double Latitude, double Longitude);
public readonly record struct DateRange(DateOnly Start, DateOnly End);
```

### Traditional Struct Usage

```csharp
public readonly struct EntityId : IEquatable<EntityId> {
    public Guid Value { get; }
    public EntityId(Guid value) => Value = value == Guid.Empty ? throw new ArgumentException("ID cannot be empty") : value;
    public static EntityId New() => new(Guid.NewGuid());
    public bool Equals(EntityId other) => Value.Equals(other.Value);
    public override bool Equals(object? obj) => obj is EntityId other && Equals(other);
    public override int GetHashCode() => Value.GetHashCode();
    public override string ToString() => Value.ToString();
    public static bool operator ==(EntityId left, EntityId right) => left.Equals(right);
    public static bool operator !=(EntityId left, EntityId right) => !left.Equals(right);
}
```

### Value Type Size Guidelines

Keep structs **under 16 bytes** for optimal performance. Larger structs incur copy overhead that negates stack allocation benefits. If a struct exceeds 16 bytes or contains reference types, consider using a record class instead.

### Immutability Enforcement

Mark struct fields as `readonly`; use `readonly struct` to enforce immutability across all members. Mutable structs cause subtle bugs when passed by value.

---
[Back to Overview](./OVERVIEW.md)
