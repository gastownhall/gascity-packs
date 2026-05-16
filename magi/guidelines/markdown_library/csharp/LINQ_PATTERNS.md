# LINQ and Functional Patterns

### Method Syntax Preference

Use method syntax for most LINQ operations; query syntax only when it significantly improves readability for complex joins:

```csharp
var activeOrders = orders.Where(o => o.Status == OrderStatus.Active).OrderByDescending(o => o.CreatedAt).Take(10).ToList();
```

### Deferred Execution Awareness

LINQ queries execute lazily. Materialize with `ToList()`, `ToArray()`, or `ToDictionary()` when you need to iterate multiple times:

```csharp
var results = query.ToList();
foreach (var item in results) { /* first iteration */ }
foreach (var item in results) { /* second iteration - safe */ }
```

### Avoiding Re-enumeration

Pass collections as `IReadOnlyList<T>` or `IReadOnlyCollection<T>` when multiple enumeration is expected:

```csharp
public void Process(IReadOnlyList<Order> orders) {
    if (orders.Count == 0) return;
    var total = orders.Sum(o => o.Total);
    var average = total / orders.Count;
}
```

### Aggregation Patterns

Prefer specific aggregation methods over `Aggregate`:

```csharp
var total = orders.Sum(o => o.Total);
var max = orders.Max(o => o.CreatedAt);
var grouped = orders.GroupBy(o => o.CustomerId).ToDictionary(g => g.Key, g => g.ToList());
```

### Null Handling in LINQ

```csharp
var names = users?.Select(u => u.Name).Where(n => !string.IsNullOrEmpty(n)).ToList() ?? [];
var first = orders.FirstOrDefault(o => o.Id == id)?.CustomerName ?? "Unknown";
```

---
[Back to Overview](./OVERVIEW.md)
