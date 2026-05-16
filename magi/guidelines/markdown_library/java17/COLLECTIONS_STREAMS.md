# Collections and Streams

### Immutable Collection Factories

```java
List<String> roles = List.of("admin", "user", "guest");
Set<Status> open = Set.of(Status.NEW, Status.IN_PROGRESS);
Map<String, Integer> ports = Map.of("http", 80, "https", 443);
Map<String, Integer> larger = Map.ofEntries(
    Map.entry("http", 80),
    Map.entry("https", 443),
    Map.entry("ssh", 22));
```

These factories return unmodifiable instances that throw `UnsupportedOperationException` on mutation attempts. Forbidden — `Collections.unmodifiableList(new ArrayList<>(...))` creates a view over a mutable list that can still be mutated via the original reference.

### List.copyOf for Defensive Copies

```java
public final class Order {
    private final List<LineItem> items;

    public Order(List<LineItem> items) {
        this.items = List.copyOf(items);   // immutable defensive copy
    }
}
```

Accept `Collection`/`List`/`Set`/`Map` interfaces as parameter types, not concrete implementations.

### Streams for Declarative Transformations

```java
List<String> activeEmails = users.stream()
    .filter(User::isActive)
    .map(User::email)
    .sorted()
    .toList();
```

Use streams for filtering, mapping, reducing, grouping, collecting. Use traditional loops for operations with side effects (I/O, checked exceptions, complex stateful accumulation). Streams that contain try-catch blocks, modify external state, or exceed 5–6 chained operations should be refactored to a loop or broken into named intermediate operations.

### Stream.toList() for Unmodifiable Lists

Use `Stream.toList()` (Java 16+) instead of `.collect(Collectors.toList())` for collecting to unmodifiable lists. When a mutable list is needed, use `.collect(Collectors.toCollection(ArrayList::new))`.

### Parallel Streams Sparingly

Parallel streams only for CPU-bound operations on large datasets (10,000+ elements) where the transformation per element is expensive and the operation is stateless. Parallel streams introduce thread-pool contention (they share the common `ForkJoinPool`), ordering complexity, and debugging difficulty. **Measure before parallelizing.** Most stream operations are I/O-bound or operate on small collections and gain nothing from parallelism.

---
[Back to Overview](./OVERVIEW.md)
