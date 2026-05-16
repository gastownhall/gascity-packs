# Swift Coding Style Library

**Swift:** 5.9+ minimum, 6.0+ recommended. **Platforms:** iOS, macOS, watchOS, tvOS, visionOS.

These guidelines define strict, readable, and consistent formatting for all Swift source code, optimizing for:

- **Type Safety** — Leverage the compiler as your first line of defense; eliminate runtime failures through exhaustive type modeling.
- **Value Semantics** — Prefer structs and enums; use classes only when reference semantics are explicitly required.
- **Protocol-Oriented Design** — Compose behavior through protocols rather than inheritance hierarchies.
- **Memory Correctness** — Zero retain cycles, no dangling references, explicit ownership at all boundaries.
- **Concurrency Safety** — Actor isolation, Sendable conformance, structured concurrency by default.

## Critical Mandates (Read First)

- **Compile-Time Guarantees Over Runtime Checks** — If the compiler can enforce a constraint, encode it in the type system. Every `fatalError`, forced unwrap, or `as!` cast represents a gap in your type design that should be closed.
- **Compact First, Multi-line When Necessary** — Single-line forms preferred when under 200 characters; break only when readability demands it.
- **No Force Unwrap in Production** — `!`, `try!`, and IUOs are prohibited outside framework-guaranteed contexts.
- **Shakedown Required Before Submission** — A §21 shakedown MUST pass after every triggering change before TestFlight/App Store submission.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Project Structure and Organization](./PROJECT_STRUCTURE.md)
3. [Line Length and Formatting](./FORMATTING.md)
4. [Naming Conventions](./NAMING.md)
5. [Type System and Protocols](./TYPE_SYSTEM.md)
6. [Memory Management](./MEMORY_MANAGEMENT.md)
7. [Concurrency and Async/Await](./CONCURRENCY.md)
8. [Error Handling](./ERROR_HANDLING.md)
9. [Optionals and Unwrapping](./OPTIONALS.md)
10. [Collections and Functional Patterns](./COLLECTIONS.md)
11. [SwiftUI Patterns](./SWIFTUI.md)
12. [UIKit Patterns](./UIKIT.md)
13. [Testing Strategy](./TESTING.md)
14. [Swift Macros](./MACROS.md)
15. [Swift Package Manager](./PACKAGE_MANAGER.md)
16. [Performance Optimization](./PERFORMANCE.md)
17. [Advanced Patterns](./ADVANCED_PATTERNS.md)
18. [Documentation](./DOCUMENTATION.md)
19. [Tooling](./TOOLING.md)
20. [Migration Guidance](./MIGRATION.md)
21. [Shakedown — Integration Validation](./SHAKEDOWN.md)
22. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
23. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
24. [Required Practices](./REQUIRED_PRACTICES.md)
25. [Style Summary](./STYLE_SUMMARY.md)
