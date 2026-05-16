# C# Coding Guidelines Library

This directory contains an expanded, modularized version of the C# Coding Guidelines. Apply universally to all C# source code (C# 12+ / .NET 8+).

## Critical Mandates (Read First)
- **NEVER FUCKING DOWNGRADE .NET FROM CORE net10.0**!!!!!!!!!!!!!!!
- **NEVER USE PLACEHOLDERS**
- **NEVER USE STUBS!!!!!!!!!!**
- **NEVER** SIMPLIFY CODE, PROJECTS, DEPLOYMENTS, OR ANYTHING **EVER**
- **UNDER NO CIRCUMSTANCES IS `NotImplementedException` ACCEPTABLE!!!!!!!**
- **Compile-Time Guarantees Over Runtime Checks** — `NullReferenceException` in production represents a failure.
- **Compact First, Multi-line When Necessary** — single-line forms preferred when they fit within 250 characters.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Type safety, horizontal density, immutability, explicitness, performance, no downgrade, no placeholders.
2. [Project Structure and Organization](./PROJECT_STRUCTURE.md) — Solution layout, dependencies, file organization, naming, internal access.
3. [Line Length and Formatting](./LINE_FORMATTING.md) — 250-char limit, single-line preference, multi-line, trailing commas, indentation.
4. [Using Directives and Namespace Management](./USING_DIRECTIVES.md) — Order, global usings, file-scoped namespaces, aliases.
5. [Type Design and Member Definitions](./TYPE_DESIGN.md) — Class principles, member ordering, signatures, properties, primary constructors, required members, collection expressions, expression-bodied.
6. [Records, Structs, and Value Types](./RECORDS_STRUCTS.md) — Selection, decision tree, record struct, traditional struct, size, immutability.
7. [Generics and Type Constraints](./GENERICS.md) — Constraint ordering, variance, generic methods, static abstract members.
8. [Pattern Matching and Switch Expressions](./PATTERN_MATCHING.md) — Switch expressions, property/type/list patterns, guard clauses.
9. [LINQ and Functional Patterns](./LINQ_PATTERNS.md) — Method syntax, deferred execution, re-enumeration, aggregation, null handling.
10. [Async/Await and Concurrency](./ASYNC_CONCURRENCY.md) — Method design, blocking, ConfigureAwait, parallelism, ValueTask, Channels, async disposable.
11. [Nullable Reference Types](./NULLABLE_TYPES.md) — Enable, annotation patterns, null-forgiving operator.
12. [Error Handling and Result Patterns](./ERROR_HANDLING.md) — Exceptions, guard clauses, Result pattern, wrapping, never swallow.
13. [Dependency Injection and Composition](./DEPENDENCY_INJECTION.md) — Constructor injection, registration, lifetime, segregation, keyed services, options.
14. [Entity Framework Core Patterns](./EF_CORE.md) — Async, AsNoTracking, AsSplitQuery, compiled queries.
15. [Memory Management and Performance](./MEMORY_PERFORMANCE.md) — Span/Memory, String.Create, ArrayPool, object pooling, disposal.
16. [Serialization and Data Contracts](./SERIALIZATION.md) — System.Text.Json config, source generation, versioning, enums.
17. [Logging and Observability](./LOGGING_OBSERVABILITY.md) — Structured logging, levels, source generators, correlation, metrics.
18. [Configuration Management](./CONFIGURATION.md) — Sources, strongly-typed options, secrets, validation.
19. [Minimal APIs](./MINIMAL_APIS.md) — Route groups, TypedResults.
20. [Source Generators](./SOURCE_GENERATORS.md) — JSON and logging source generation.
21. [Testing Strategy](./TESTING_STRATEGY.md) — Test project structure, naming, AAA, builders, integration testing.
22. [Security Practices](./SECURITY.md) — Input validation, SQL injection, secrets, auth.
23. [Build Configuration and Tooling](./BUILD_TOOLING.md) — Directory.Build.props, central package management, EditorConfig, analyzers.
24. [Shakedown](./SHAKEDOWN.md) — Definition, three forms, triggers, validation, execution, classification, anti-patterns.
25. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
26. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do / Always Do lists.
27. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
