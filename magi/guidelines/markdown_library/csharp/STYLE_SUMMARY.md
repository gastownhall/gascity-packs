# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Line Length | Maximum 250 characters |
| Indentation | 4 spaces; no tabs |
| Braces | Opening on same line; closing on own line |
| Using Directives | System → Microsoft → Third-party → Internal → Aliases; grouped by blank lines |
| Namespaces | File-scoped exclusively |
| Type Modifiers | Prefer `sealed`; explicit access modifiers always |
| Properties | Auto-properties with `init`; expression-bodied for computed |
| Records | Default for DTOs, events, value objects; `readonly record struct` for small values |
| Nullability | Enabled; avoid `!` except at interop boundaries |
| Async | `Async` suffix; accept `CancellationToken`; `ConfigureAwait(false)` in libraries |
| Error Handling | Guard clauses; specific exceptions; Result pattern for expected failures |
| Dependency Injection | Constructor injection; no service locator; appropriate lifetimes |
| EF Core | Always async; `AsNoTracking` for read-only; `AsSplitQuery` for multi-include; compiled queries for hot paths |
| LINQ | Method syntax; materialize when iterating multiple times |
| Pattern Matching | Switch expressions; property patterns; exhaustive matching |
| Serialization | `System.Text.Json` with source generators for AOT |
| Logging | Structured with message templates; source-generated for performance |
| Testing | Arrange-Act-Assert; descriptive names; builders for complex data |
| Configuration | Options pattern with validation; secrets via Key Vault or user secrets |
| Minimal APIs | Route groups; `TypedResults` for compile-time safety |
| Build | Central package management; `Directory.Build.props`; warnings as errors |
| Shakedown | Real `IHost` + `Testcontainers.NET` + eight categories + classified outcome |
| Defense in Depth | Nullable + warnings-as-errors + tests + validation + CI + telemetry + shakedown |

---

Following these guidelines produces C# code that is type-safe, performant, maintainable, and production-ready. The compiler becomes your first line of defense when you enable strict analysis and treat warnings as errors. Embrace immutability, leverage pattern matching, and design for testability from the start. Every public API should be documented, every async method should accept cancellation, and every dependency should be injected. Shakedown the assembled `IHost` against real infrastructure before traffic — unit tests cannot detect what shakedown does.

**NEVER** SIMPLIFY CODE, PROJECTS, DEPLOYMENTS, OR ANYTHING **EVER**
- Trying to "simplify" because something doesn't compile or run is an **ANTI-PATTERN**
- Simplifying is "giving up" and causes the request to be **REJECTED** as you will have **FAILED**
- **DOWNGRADING** IS EQUALLY AS FUCKING STUPID AND **REJECTED**

**UNDER NO CIRCUMSTANCES ARE YOU TO RANDOMLY CHANGE CODE AND/OR SET VALUES BASED ON INCORRECT / INACCURATE DATA**
**UNDER NO CIRCUMSTANCES ARE YOU TO REMOVE CODE UNNECESSARILY!!!!!!!!**
**UNDER NO CIRCUMSTANCES IS `NotImplementedException` ACCEPTABLE!!!!!!!**

---
[Back to Overview](./OVERVIEW.md)
