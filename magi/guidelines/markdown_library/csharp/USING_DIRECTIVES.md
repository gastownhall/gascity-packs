# Using Directives and Namespace Management

### Organization Order

1. `System.*` namespaces (BCL fundamentals)
2. `Microsoft.*` namespaces (framework and platform)
3. Third-party namespaces (NuGet packages)
4. Internal project namespaces
5. Alias using statements

Separate groups with a single blank line.

### Global Usings

Define ubiquitous namespaces in a single `GlobalUsings.cs` at the project root:

```csharp
global using System.Collections.Immutable;
global using System.Diagnostics.CodeAnalysis;
global using Microsoft.Extensions.Logging;
global using Company.Product.Core.Entities;
global using Company.Product.Core.ValueObjects;
```

**Reserve global usings for namespaces used in more than 50% of files.** Over-globalization hides dependencies and complicates code navigation.

### File-Scoped Namespaces

Use file-scoped namespaces exclusively. Block-scoped namespaces waste indentation:

```csharp
namespace Company.Product.Core.Services;

public sealed class OrderService : IOrderService {
    // Implementation
}
```

### Using Aliases

```csharp
using OrderDict = System.Collections.Generic.Dictionary<string, Company.Product.Core.Entities.Order>;
using JsonOptions = System.Text.Json.JsonSerializerOptions;
```

Avoid aliases purely for brevity.

---
[Back to Overview](./OVERVIEW.md)
