# Security Practices

### Input Validation

```csharp
public sealed class CreateOrderCommandValidator : AbstractValidator<CreateOrderCommand> {
    public CreateOrderCommandValidator() {
        RuleFor(x => x.CustomerId).NotEmpty().MaximumLength(50);
        RuleFor(x => x.Lines).NotEmpty().Must(lines => lines.All(l => l.Quantity > 0));
        RuleFor(x => x.ShippingAddress).NotNull().SetValidator(new AddressValidator());
    }
}
```

### SQL Injection Prevention

Always use parameterized queries:

```csharp
var orders = await context.Orders.Where(o => o.CustomerId == customerId && o.Status == status).ToListAsync(ct);

await context.Database.ExecuteSqlAsync($"UPDATE Orders SET Status = {newStatus} WHERE Id = {orderId}", ct);
```

**Never concatenate user input into SQL strings.**

### Secrets Handling

```csharp
using var key = new SecureString();
foreach (var c in password) key.AppendChar(c);
key.MakeReadOnly();
```

Use `IDataProtector` for at-rest encryption:

```csharp
var protector = _dataProtectionProvider.CreateProtector("Tokens");
var protectedToken = protector.Protect(token);
var unprotectedToken = protector.Unprotect(protectedToken);
```

### Authentication and Authorization

```csharp
services.AddAuthorization(options => {
    options.AddPolicy("AdminOnly", policy => policy.RequireRole("Admin"));
    options.AddPolicy("CanManageOrders", policy => policy.RequireClaim("permission", "orders:manage"));
});

[Authorize(Policy = "CanManageOrders")]
public async Task<IActionResult> DeleteOrder(Guid id) { }
```

---
[Back to Overview](./OVERVIEW.md)
