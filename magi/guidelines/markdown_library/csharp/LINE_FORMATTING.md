# Line Length and Formatting

### Maximum Line Length

**Hard limit**: 250 characters per line. Modern displays and tooling accommodate wide lines; horizontal density reduces vertical scrolling and keeps related logic visible.

### Single-line Preference

Keep on one line when under 250 characters:
- Method signatures including parameters, generics, constraints, and return type
- Property declarations including expression-bodied getters
- Simple object and collection initializers
- Using directives
- Lambda expressions with single-expression bodies
- Ternary conditionals with short branches

### Multi-line Formatting

```csharp
public async Task<Result<OrderConfirmation>> ProcessOrderAsync(
    OrderRequest request,
    PaymentDetails payment,
    ShippingAddress address,
    CancellationToken cancellationToken,
) {
    // Implementation
}
```

### Trailing Commas

Required in multi-line constructs:
- Object initializers, collection initializers, array initializers
- Enum member lists
- Multi-line parameter lists (C# 12+)

Trailing commas produce cleaner diffs when adding items.

### Indentation and Spacing

- 4 spaces per indentation level; **tabs are prohibited**
- Single blank line between using groups, between members, and before return statements in complex methods
- No blank lines at the start or end of blocks
- No trailing whitespace
- Opening brace `{` on the same line as the declaration
- Closing brace `}` on its own line for multi-line blocks

---
[Back to Overview](./OVERVIEW.md)
