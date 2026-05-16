# Project Structure and Organization

### Solution Layout

```
Solution/
├── src/
│   ├── Company.Product.Api/
│   ├── Company.Product.Core/
│   ├── Company.Product.Infrastructure/
│   └── Company.Product.Worker/
├── tests/
│   ├── Company.Product.Core.Tests/
│   ├── Company.Product.Api.Tests/
│   └── Company.Product.Integration.Tests/
├── tools/
│   └── Company.Product.Migrations/
├── Directory.Build.props
├── Directory.Packages.props
└── Solution.sln
```

### Project Dependencies

Follow the dependency inversion principle through project layering:

- **Core/Domain**: Zero external dependencies beyond BCL; defines interfaces, entities, value objects, domain logic
- **Infrastructure**: Implements Core interfaces; depends on external packages (EF Core, HTTP clients, cloud SDKs)
- **Api/Worker**: Composition root; references Core and Infrastructure; configures DI and middleware
- **Tests**: Mirror source structure

**Never allow Infrastructure to depend on Api.** **Never allow Core to depend on Infrastructure.** Violations indicate architectural drift that must be corrected immediately.

### File Organization Within Projects

```
Company.Product.Core/
├── Entities/
├── ValueObjects/
├── Services/
├── Repositories/
├── Events/
└── Exceptions/
```

### File Naming and Type Placement

- **One public type per file**; file name matches type name exactly
- Interfaces reside in the same directory as their primary implementations or in a dedicated `Abstractions` folder
- Extensions live in an `Extensions` folder with naming pattern `{ExtendedType}Extensions.cs`
- Test files mirror source files: `OrderService.cs` → `OrderServiceTests.cs`

### Internal Access Modifier Usage

Use `internal` for types that should not escape assembly boundaries. Combine with `InternalsVisibleTo` for test access:

```csharp
[assembly: InternalsVisibleTo("Company.Product.Core.Tests")]
```

---
[Back to Overview](./OVERVIEW.md)
