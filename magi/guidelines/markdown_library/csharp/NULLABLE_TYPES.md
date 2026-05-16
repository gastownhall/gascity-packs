# Nullable Reference Types

### Enable Globally

```xml
<Nullable>enable</Nullable>
<TreatWarningsAsErrors>true</TreatWarningsAsErrors>
```

### Annotation Patterns

```csharp
// Nullable return type when null is valid
public async Task<Order?> FindOrderAsync(Guid id, CancellationToken ct);

// Non-nullable when guaranteed to return value
public async Task<Order> GetOrderAsync(Guid id, CancellationToken ct) {
    return await FindOrderAsync(id, ct)
        ?? throw new OrderNotFoundException(id);
}

// Nullable parameters when null is acceptable
public void LogMessage(string message, Exception? exception = null);
```

### Null-Forgiving Operator (`!`)

**Minimize usage.** Allowed contexts:
- Interop boundaries with legacy code
- After explicit null check that compiler cannot infer

```csharp
if (IsValid(value)) {
    // Compiler cannot infer that value is non-null after IsValid
    ProcessValue(value!);
}
```

---
[Back to Overview](./OVERVIEW.md)
