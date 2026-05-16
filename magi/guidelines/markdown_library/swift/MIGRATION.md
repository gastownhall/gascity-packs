# Migration Guidance

### Swift 6 Migration

- Enable strict concurrency checking incrementally (`Minimal` → `Targeted` → `Complete`).
- Audit and fix all Sendable conformance.
- Review actor isolation boundaries — many `nonisolated` annotations may be needed.

### Modernizing Legacy Code

| Legacy pattern | Modern replacement |
|:---------------|:-------------------|
| Completion handlers | `async`/`await` |
| `DispatchQueue` | actors or Tasks |
| `ObservableObject` + `@Published` | `@Observable` macro |
| `NavigationLink(destination:)` | `NavigationStack` + `navigationDestination(for:)` |
| XCTest method-based tests | Swift Testing `@Test` attributes |

---
[Back to Overview](./OVERVIEW.md)
