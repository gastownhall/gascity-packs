# Core Principles

These guidelines define strict, readable, and consistent formatting for all Swift source code, optimizing for:

- **Type Safety** — Leverage the compiler as your first line of defense; eliminate runtime failures through exhaustive type modeling.
- **Value Semantics** — Prefer structs and enums; use classes only when reference semantics are explicitly required.
- **Protocol-Oriented Design** — Compose behavior through protocols rather than inheritance hierarchies.
- **Memory Correctness** — Zero retain cycles, no dangling references, explicit ownership at all boundaries.
- **Concurrency Safety** — Actor isolation, Sendable conformance, structured concurrency by default.

### Primary Rule: Compile-Time Guarantees Over Runtime Checks

If the compiler can enforce a constraint, encode it in the type system. Runtime assertions indicate a modeling failure. **Every `fatalError`, forced unwrap, or `as!` cast represents a gap in your type design that should be closed.**

### Secondary Rule: Compact First, Multi-line When Necessary

Use horizontal space efficiently. Single-line forms are preferred when under the character limit. Break lines only when:

- Line exceeds 200 characters.
- Readability demands it for complex generic constraints or closures.
- Multiple distinct logical operations exist on the same line.

---
[Back to Overview](./OVERVIEW.md)
