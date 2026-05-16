# Core Principles

These guidelines define strict conventions for Java 17 LTS development covering modern language features (records, sealed classes, pattern matching, text blocks, switch expressions), type system discipline, null safety, immutability patterns, collections and streams, concurrency, exception handling, API design, security hardening, serialization safety, module system usage, testing strategy, build tooling, GC tuning, logging, and Spring Boot integration patterns.

**Scope:** All Java 17 codebases — microservices, libraries, CLI tools, batch processors, backend APIs. Greenfield Java 17 work and migrations from Java 8/11.

**Runtime:** Java 17 LTS (OpenJDK 17 / Eclipse Temurin 17 / Amazon Corretto 17), Maven 3.9+ or Gradle 8+, JUnit 5.10+, Spring Boot 3.x.

### Modern Java First

Java 17 provides records, sealed classes, pattern matching for `instanceof`, switch expressions, text blocks, and enhanced APIs. Use them. Code that reads like Java 8 when Java 17 features solve the problem more clearly is technical debt disguised as familiarity. Every new class, method, and module starts from the Java 17 baseline.

### Immutability by Default

Mutable state is the root cause of the majority of concurrency bugs, cache invalidation errors, and defensive-copy oversights. Default to:

- Records for data carriers
- `List.of` / `Map.of` / `Set.of` for collections
- `final` fields
- Unmodifiable views

Mutability requires explicit justification — builder patterns, accumulators in stream reductions, or measured hot-path optimizations.

### Null Is a Bug, Not a Value

Returning `null` from methods, accepting `null` parameters, and storing `null` in collections creates invisible failure modes that surface as `NullPointerException` at runtime, far from the source. Use:

- `Optional` for absent return values
- `@NonNull` / `@Nullable` annotations to document null contracts at API boundaries
- `Objects.requireNonNull` in constructors and public method entries

### Type Safety Over Stringly-Typed

A method `(String userId, String email, String orderId)` can be called with arguments in any order; the compiler stays silent. Use records, value objects, or enums to give distinct types to distinct concepts.

### Fail Fast, Fail Loud

Validate inputs at public API boundaries:

- `IllegalArgumentException` for invalid arguments
- `IllegalStateException` for invalid object state
- `NullPointerException` (via `Objects.requireNonNull`) for null arguments

**Never silently swallow exceptions, return default values for invalid inputs, or log-and-continue when the operation cannot succeed.**

### Foundational Rules

- All new code targets Java 17 language level. Source and target compatibility set to 17. **Preview features (`--enable-preview`) are prohibited in production builds.**
- Every public method documents its null contract. Non-null parameters are annotated `@NonNull` and validated with `Objects.requireNonNull` at entry. Return values that may be absent use `Optional`. Returning `null` from a method that does not declare `@Nullable` is a bug.

---
[Back to Overview](./OVERVIEW.md)
