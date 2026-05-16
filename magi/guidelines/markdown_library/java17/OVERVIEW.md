# Java 17 Development Library

These guidelines define strict conventions for Java 17 LTS development covering modern language features (records, sealed classes, pattern matching, text blocks, switch expressions), type system discipline, null safety, immutability patterns, collections and streams, concurrency, exception handling, API design, security hardening, serialization safety, module system usage, testing strategy, build tooling, GC tuning, logging, and Spring Boot integration patterns.

## Critical Mandates (Read First)
- **Modern Java First** — use records, sealed classes, pattern matching, switch expressions, text blocks; preview features prohibited.
- **Immutability by Default** — records, `List.of`/`Map.of`/`Set.of`, `final` fields.
- **Null Is a Bug** — `Optional` for absent returns; `@NonNull`/`@Nullable`; `Objects.requireNonNull`.
- **Type Safety Over Stringly-Typed** — distinct types for distinct concepts.
- **Fail Fast, Fail Loud** — validate at boundaries; never silently swallow.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Records](./RECORDS.md)
3. [Sealed Classes and Interfaces](./SEALED_CLASSES.md)
4. [Pattern Matching and Switch Expressions](./PATTERN_MATCHING.md)
5. [Text Blocks and String Handling](./TEXT_BLOCKS.md)
6. [Null Safety and Optional](./NULL_SAFETY.md)
7. [Collections and Streams](./COLLECTIONS_STREAMS.md)
8. [Concurrency](./CONCURRENCY.md)
9. [Exception Handling](./EXCEPTION_HANDLING.md)
10. [API Design](./API_DESIGN.md)
11. [Security](./SECURITY.md)
12. [Logging](./LOGGING.md)
13. [Testing](./TESTING.md)
14. [Shakedown — Integration Validation](./SHAKEDOWN.md)
15. [Build and Dependency Management](./BUILD_DEPENDENCY_MANAGEMENT.md)
16. [Performance and GC Tuning](./PERFORMANCE_GC.md)
17. [Module System (JPMS)](./MODULE_SYSTEM.md)
18. [Spring Boot Integration](./SPRING_BOOT.md)
19. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
20. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
21. [Required Practices](./REQUIRED_PRACTICES.md)
22. [Style Summary](./STYLE_SUMMARY.md)
