# Core Principles

These guidelines define strict, performant, and maintainable patterns for all C# source code (C# 12+ / .NET 8+), optimizing for:

- **Type Safety**: Leverage nullable reference types, pattern matching, and strong typing to catch errors at compile time rather than runtime
- **Horizontal Density**: Maximize line utilization up to 250 characters; single-line forms are preferred when they fit
- **Immutability by Default**: Prefer records, init-only setters, and readonly collections; mutable state requires explicit justification
- **Explicit over Implicit**: No magic strings, no hidden dependencies, no ambient state; every behavior is declared and traceable
- **Performance Awareness**: Understand allocation costs, prefer value types for small data, use `Span<T>` and `Memory<T>` where appropriate
- **No Downgrade**: Never downgrade .NET versions or NuGet packages. Downgrading breaks compatibility and represents failure.
- **No Placeholders**: No placeholder, stub, or TODO code in production. `NotImplementedException` is forbidden. Method stubs returning default values are forbidden.

### Primary Rule: Compile-Time Guarantees Over Runtime Checks

The C# compiler is a powerful ally. Enable strict nullable analysis, treat warnings as errors, and encode business rules in the type system. **A `NullReferenceException` in production represents a failure to leverage the type system.** Pattern matching exhaustiveness, sealed hierarchies, and discriminated unions via records eliminate entire categories of runtime failures.

### Secondary Rule: Compact First, Multi-line When Necessary

Prefer single-line forms when they fit within 250 characters. Break across lines only when the line would exceed the limit, when nesting or argument complexity reduces clarity, or when multiple statements are required.

### Language Version Strategy

Target C# 12 with .NET 8 as the minimum platform. Use language features purposefully:

- **Primary constructors**: For simple DI and parameter capture
- **Collection expressions**: For concise array and list initialization
- **Required members**: For enforcing initialization contracts
- **File-scoped types**: For implementation details that shouldn't escape the file
- **Raw string literals**: For embedded SQL, JSON, or multi-line content
- **Pattern matching**: For type-safe branching and deconstruction

---
[Back to Overview](./OVERVIEW.md)
