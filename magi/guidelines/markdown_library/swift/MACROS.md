# Swift Macros

Swift macros (Swift 5.9+) reduce boilerplate and enable DSLs at compile time.

| Type | Use |
|:-----|:----|
| Attached macros | Boilerplate reduction (e.g., `@Observable`, `@AddAsync`) |
| Freestanding macros | DSLs and code generation |

```swift
// Built-in macro
@Observable
final class ViewModel {
    var items: [Item] = []
}

// Custom attached macro
@AddAsync
protocol DataService {
    func fetchData() throws -> Data
}
// Expands to include:
// func fetchData() async throws -> Data
```

### Macro Definition Guidelines

- Implement custom macros in a **separate module**.
- Thoroughly test macro expansions.
- Provide helpful diagnostic error messages.

---
[Back to Overview](./OVERVIEW.md)
