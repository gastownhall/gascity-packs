# Pattern Matching and Switch Expressions

### Switch Expression Preference

```csharp
public static string GetStatusMessage(OrderStatus status) => status switch {
    OrderStatus.Pending => "Awaiting confirmation",
    OrderStatus.Confirmed => "Order confirmed",
    OrderStatus.Shipped => "In transit",
    OrderStatus.Delivered => "Delivered",
    OrderStatus.Cancelled => "Order cancelled",
    _ => throw new ArgumentOutOfRangeException(nameof(status)),
};
```

### Property Patterns

```csharp
public decimal CalculateDiscount(Order order) => order switch {
    { Total: > 1000, CustomerTier: CustomerTier.Gold } => order.Total * 0.15m,
    { Total: > 500, CustomerTier: CustomerTier.Gold } => order.Total * 0.10m,
    { Total: > 500 } => order.Total * 0.05m,
    _ => 0m,
};
```

### Type Patterns

```csharp
public string Describe(object value) => value switch {
    null => "null",
    string s => $"string: \"{s}\"",
    int i => $"int: {i}",
    IEnumerable<object> items => $"collection: [{string.Join(", ", items)}]",
    _ => $"unknown: {value}",
};
```

### List Patterns

```csharp
public string DescribeList(int[] numbers) => numbers switch {
    [] => "empty",
    [var single] => $"single element: {single}",
    [var first, .., var last] => $"first: {first}, last: {last}",
};
```

### Guard Clauses with When

```csharp
public string Classify(int value) => value switch {
    < 0 => "negative",
    0 => "zero",
    > 0 and < 10 => "small positive",
    >= 10 and < 100 => "medium positive",
    _ => "large positive",
};
```

---
[Back to Overview](./OVERVIEW.md)
