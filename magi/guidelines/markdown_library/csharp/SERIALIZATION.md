# Serialization and Data Contracts

### System.Text.Json Configuration

```csharp
public static class JsonConfig {
    public static readonly JsonSerializerOptions Default = new() {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true,
        WriteIndented = false,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.CamelCase) },
    };
}
```

### Source Generation for AOT

```csharp
[JsonSerializable(typeof(Order))]
[JsonSerializable(typeof(List<Order>))]
[JsonSerializable(typeof(CreateOrderCommand))]
[JsonSourceGenerationOptions(PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase)]
public partial class AppJsonContext : JsonSerializerContext { }

var json = JsonSerializer.Serialize(order, AppJsonContext.Default.Order);
var parsed = JsonSerializer.Deserialize(json, AppJsonContext.Default.Order);
```

### Data Contract Versioning

```csharp
public sealed record OrderDto {
    public required Guid Id { get; init; }
    public required string CustomerId { get; init; }
    public required decimal Total { get; init; }
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Notes { get; init; }
    [JsonExtensionData]
    public Dictionary<string, JsonElement>? ExtensionData { get; init; }
}
```

### Enum Serialization

```csharp
[JsonConverter(typeof(JsonStringEnumConverter<OrderStatus>))]
public enum OrderStatus { Pending, Confirmed, Shipped, Delivered, Cancelled }
```

---
[Back to Overview](./OVERVIEW.md)
