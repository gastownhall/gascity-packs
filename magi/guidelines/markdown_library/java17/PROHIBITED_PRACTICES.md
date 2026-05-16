# Prohibited Practices

### Never Do

- Use Java serialization (`ObjectInputStream`/`ObjectOutputStream`) for new data interchange — use JSON, Protobuf, or Avro.
- Create raw `Thread` instances for application logic — use `ExecutorService` or `CompletableFuture`.
- Return `null` from methods that return collections — return empty collections.
- Return `null` from methods where `Optional` is the appropriate return type.
- Use `Optional` as a field type, method parameter, or collection element.
- Catch `Exception` or `Throwable` except at top-level entry points.
- Catch `InterruptedException` without re-interrupting the thread.
- Write POJOs with boilerplate getters/setters/equals/hashCode when a record suffices.
- Concatenate variables into SQL strings — use `PreparedStatement`.
- Use `System.out.println` or `System.err.println` for application logging.
- Use string concatenation in log statements — use parameterized messages.
- Use MD5, SHA-1, DES, 3DES, RC4, or `java.util.Random` for security operations.
- Use the traditional instanceof-then-explicit-cast pattern — use pattern matching instanceof.
- Use switch statements (with fall-through) when a switch expression (with arrows) produces a value.
- Use `--enable-preview` features in production builds.
- Add `--add-opens` / `--add-exports` JVM flags without a documented migration plan for removal.
- Log passwords, tokens, credit card numbers, SSNs, or API keys.
- Use `@Autowired` field injection in Spring beans — use constructor injection.
- Override `equals`/`hashCode` on records (without explicit, documented reason).
- Mock the class under test or value records.
- Tune HikariCP, JVM flags, Kafka producer settings, or GC options during shakedown.
- Write shakedown artifacts to `/tmp`, `java.io.tmpdir`, or any system temp directory.

---
[Back to Overview](./OVERVIEW.md)
