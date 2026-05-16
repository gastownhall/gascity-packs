# Required Practices

### Always Do

- Use records for all data carrier classes: DTOs, value objects, API payloads, event structures.
- Use sealed interfaces for domain types with fixed variant sets. Combine with records for algebraic data types.
- Use pattern matching for `instanceof` in all type-check-and-cast scenarios.
- Use switch expressions (arrow syntax) for all value-producing switches.
- Use text blocks for multi-line string literals (SQL, JSON, HTML, XML).
- Document null contracts with `@NonNull` / `@Nullable` annotations. Validate with `Objects.requireNonNull`.
- Return `Optional` for methods that may not produce a result. Never return `null`.
- Use `List.of` / `Set.of` / `Map.of` for immutable collections. Use `List.copyOf` for defensive copies.
- Use try-with-resources for all `AutoCloseable` resources.
- Use `PreparedStatement` for all parameterized SQL. Never concatenate variables into queries.
- Use SLF4J with parameterized messages. Configure Logback or Log4j2 as implementation.
- Use JUnit 5 for all new tests. Test behavior via public APIs, not implementation details.
- Run dependency vulnerability scanning in CI. Fail on high/critical severity.
- Configure the compiler to treat warnings as errors (`-Xlint:all -Werror`).
- Shut down `ExecutorService` instances explicitly. Register shutdown hooks for long-lived pools.
- Profile with JFR/JMH before performance optimization. No optimization without measurement.
- Use constructor injection for all Spring beans. Make dependencies explicit and `final`.
- Run a §14 shakedown after every change that affects bean wiring, migrations, brokers, or composition root.

---
[Back to Overview](./OVERVIEW.md)
