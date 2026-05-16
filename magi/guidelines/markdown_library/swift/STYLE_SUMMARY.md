# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Line Length | Maximum 200 characters |
| Indentation | 4 spaces; no tabs |
| Braces | Opening on same line; closing on own line |
| Access Control | Explicit on all declarations; most restrictive feasible |
| Types | Prefer `struct`/`enum`; `class` only for identity or inheritance; `actor` for shared mutable state |
| Optionals | Unwrap with `guard let`/`if let`; no force unwraps in production |
| Error Handling | Use `throws`; catch specific errors; never swallow |
| Concurrency | Swift Concurrency with `async`/`await`; actors for synchronization |
| Memory | `weak` for delegates; explicit capture lists; verify `deinit` fires |
| Closures | Trailing closure syntax; explicit capture semantics |
| SwiftUI State | `@State` local, `@StateObject` owned, `@ObservedObject` injected |
| UIKit Delegates | Always `weak`; use modern diffable data sources |
| Testing | Protocol-based DI; async tests; descriptive naming; Swift Testing `@Test` for Swift 6+ |
| Macros | `@Observable` over `ObservableObject`; custom macros in separate modules |
| SPM | Explicit dependencies; semantic versioning; modular feature packages |
| Performance | Measure before optimizing; `final` classes; WMO for release |
| Documentation | `///` comments on public APIs; no orphan TODOs |
| Trailing Commas | Required in multi-line collections and parameter lists |
| Naming | Types `PascalCase`; members `camelCase`; no abbreviations |
| Tooling | `.swiftformat` + `.swiftlint.yml` enforced in CI |
| Migration | Swift 6 strict concurrency; `@Observable` over `ObservableObject`; async/await over completion handlers |
| Shakedown | Real backends + real Keychain + real APNs; pass / fail-blocking / fail-nonblocking / inconclusive; four artifacts |
| Defense in Depth | Strict concurrency + lint/format + XCTest + Instruments + clean-CI + crash reporting + shakedown |
| Rule of Three | Unit tests + UI tests + crash telemetry MUST agree before submission |

---

Following these rules yields Swift code that is type-safe, memory-correct, concurrency-safe, and production-ready. The compiler becomes your collaborator — not your adversary — when you encode invariants in the type system and follow these patterns consistently.

**Apply this style universally to all `*.swift` files across the codebase.**

---
[Back to Overview](./OVERVIEW.md)
