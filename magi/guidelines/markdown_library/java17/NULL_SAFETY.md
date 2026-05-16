# Null Safety and Optional

### Optional as Return Type for Possibly-Absent Values

```java
public Optional<User> findById(UUID id) {
    return jdbc.query("SELECT * FROM users WHERE id = ?", USER_MAPPER, id)
               .stream()
               .findFirst();
}

// Caller
User user = findById(id).orElseThrow(() -> new UserNotFoundException(id));
```

Repository lookups (`findById`), configuration values (`getProperty`), and search operations return `Optional`. Never return `null`. Callers use `map`/`flatMap`/`orElse`/`orElseThrow` to handle absence explicitly.

### Optional Is Not a Field, Parameter, or Collection Element

`Optional` is a return type, not a general-purpose container. Forbidden:

- `private Optional<String> name;` — fields use `@Nullable` for the rare nullable case, prefer non-null fields with defaults.
- `void set(Optional<String> name)` — use method overloading or a dedicated parameter object.
- `List<Optional<User>> users` — collections never contain `Optional`.
- `Map<K, Optional<V>>` — same rule.

### Validate Non-Null Parameters at Boundaries

```java
public OrderResult placeOrder(OrderRequest request, User user) {
    Objects.requireNonNull(request, "request must not be null");
    Objects.requireNonNull(user, "user must not be null");
    // proceed
}
```

Fails at the entry point with a descriptive message rather than failing deep in the call stack. Record compact constructors validate components the same way.

### Use @NonNull and @Nullable Annotations

Use `@NonNull` and `@Nullable` from `org.jetbrains.annotations`, `jakarta.annotation`, or `org.checkerframework.checker.nullness.qual` on all public API methods. These annotations document the null contract and enable static analysis (IntelliJ inspections, NullAway, Checker Framework, SpotBugs) to catch null violations at compile time.

### Enhanced NPE Messages (JEP 358)

Java 17's helpful NPE messages are enabled by default. They include the exact variable or expression that was null. Verify `-XX:+ShowCodeDetailsInExceptionMessages` is not explicitly disabled.

---
[Back to Overview](./OVERVIEW.md)
