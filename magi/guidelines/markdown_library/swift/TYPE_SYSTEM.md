# Type System and Protocols

### Value Types vs Reference Types — Decision Tree

| Question | Yes | No |
|:---------|:----|:---|
| Is identity important? | Use `class` or `actor` | Continue |
| Need inheritance? | Use `class` | Continue |
| Shared mutable state? | Use `actor` | Use `struct` or `enum` |

- **Default to structs** for data containers, configurations, immutable models.
- **Use classes** when identity matters, inheritance is needed, or Objective-C interop is required.
- **Use enums** for finite state machines, discriminated unions, namespace-like groupings.
- **Use actors** when mutable state requires synchronized access from multiple contexts.

### Protocol Design

- Keep protocols focused; a protocol with **ten requirements** is likely doing too much.
- Prefer composition over monolithic protocols: `Hashable = Equatable + hash`.
- Use protocol extensions for default implementations only when the default is universally correct.
- Associated types should have meaningful names: `associatedtype Element`, not `associatedtype T`.

### Generics

- Use generic constraints to express requirements: `where T: Codable & Sendable`.
- Prefer **opaque return types** (`some Protocol`) when the concrete type is an implementation detail.
- Use **`any Protocol`** for heterogeneous collections or when type erasure is explicitly needed.
- **Avoid over-genericizing.** If a function only ever operates on `String`, take `String`.

### Type Inference

- Let the compiler infer types when the type is obvious from context.
- Annotate explicitly when the inferred type would be `Any`, when disambiguation is needed, or in public API signatures.
- **Always annotate empty collections:** `let items: [Item] = []`.

---
[Back to Overview](./OVERVIEW.md)
