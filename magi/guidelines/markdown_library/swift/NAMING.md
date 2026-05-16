# Naming Conventions

### General Rules

| Element | Style |
|:--------|:------|
| Types, protocols, enum cases | `PascalCase` |
| Functions, methods, properties, variables | `camelCase` |
| Static constants and type properties | `camelCase` (not `SCREAMING_CASE`) |
| Generic type parameters | Single uppercase (`T`, `U`) or descriptive `PascalCase` (`Element`, `Key`) |
| Boolean properties | Prefix `is`, `has`, `should`, `can` when it reads naturally |

### Naming Semantics

- Methods with **side effects** use verb phrases: `removeAll()`, `insert(_:at:)`.
- Methods returning values **without side effects** use noun phrases or `ing`/`ed` forms: `sorted()`, `distance(to:)`.
- Factory methods start with `make`: `makeIterator()`, `makeURLRequest()`.
- Protocols describing **capability** use `-able`, `-ible`, `-ing`: `Equatable`, `Sendable`, `Loading`.
- Protocols describing **what something is** use nouns: `Collection`, `Sequence`, `Actor`.

### Argument Labels

- Omit the first argument label when the method name forms a grammatical phrase: `contains(_:)`, `append(_:)`.
- Use prepositions to clarify relationships: `insert(_:at:)`, `move(from:to:)`.
- Use `with` for configuration closures: `withAnimation(_:)`, `withTaskGroup(of:body:)`.
- **Avoid redundant type information:** `addObserver(_:)` not `addObserver(observer:)`.

---
[Back to Overview](./OVERVIEW.md)
