# Style Summary

| Element | Required Style |
|:--------|:---------------|
| **Records** | All data carriers; validate in compact constructor; immutable; combine with sealed interfaces for ADTs; Jackson-compatible |
| **Sealed Classes** | Fixed variant sets via sealed interface + `permits`; record implementations; `final`/`sealed`/`non-sealed`; omit default in switches for exhaustiveness |
| **Pattern Matching** | `instanceof` patterns replace cast-after-check; switch expressions with arrows for values; type patterns in switch are preview in 17 (standard in 21) |
| **Text Blocks** | Multi-line literals for SQL/JSON/HTML/XML; closing delimiter controls indentation; never interpolate untrusted input |
| **Null Safety** | `Optional` for absent returns; `@NonNull`/`@Nullable`; `Objects.requireNonNull` at boundaries; never `Optional` as field/param; empty collections not null |
| **Collections** | Immutable factories (`List.of`, `Set.of`, `Map.of`); defensive copies (`List.copyOf`); `Stream.toList()` for unmodifiable; parallel streams only for measured CPU-bound large datasets |
| **Concurrency** | `ExecutorService` not raw threads; `CompletableFuture` for composition; `ConcurrentHashMap` for shared state; `AtomicLong`/`LongAdder` for counters; explicit shutdown |
| **Exceptions** | Checked for recoverable; unchecked for programming errors; try-with-resources; context in messages; preserve cause chains; re-interrupt on `InterruptedException` |
| **API Design** | Program to interfaces; return empty not null; limit parameters (use records); builder for optional config; Javadoc on public APIs |
| **Security** | No Java serialization; `PreparedStatement` for SQL; AES-256-GCM/SHA-256+; `SecureRandom`; no sensitive data in logs; respect strong JDK encapsulation |
| **Logging** | SLF4J facade; parameterized messages; MDC for request context; appropriate levels; no `System.out`; no concatenation in log calls |
| **Testing** | JUnit 5; AssertJ for fluent assertions; Mockito for dependencies; `@ParameterizedTest` for data-driven; Given-When-Then; test behavior not implementation |
| **Shakedown** | `@Profile("shakedown")` `ApplicationRunner` (services) or `shakedown-it` JUnit module (libraries); Testcontainers with pinned digests; JSON classification; artifacts under `target/shakedown/` (never `/tmp`) |
| **Build** | Pin all dependency versions; BOM for coordinated sets; vulnerability scanning in CI; `-Xlint:all -Werror`; reproducible builds; enforcer plugin |
| **Performance** | G1GC default; ZGC for sub-ms pauses; JFR in production; `-Xms` equals `-Xmx`; StringDeduplication; JMH for benchmarks; measure before optimize |
| **Modules** | `module-info.java` for libraries; export only public API packages; no `--add-opens` without migration plan; JPMS enforces inter-module boundaries |
| **Spring Boot** | Spring Boot 3.x + Jakarta EE; records for DTOs and `@ConfigurationProperties`; constructor injection exclusively; native image for serverless |
| **Defense in Depth** | Compiler warnings + static analysis + JUnit + bean validation + JaCoCo coverage + CI clean build + shakedown |
| **Rule of Three** | Compiler/analyzers + tests + production telemetry MUST agree before declaring healthy |

---
[Back to Overview](./OVERVIEW.md)
