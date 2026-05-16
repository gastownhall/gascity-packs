# Concurrency

### Use ExecutorService, Not Raw Threads

```java
ExecutorService pool = Executors.newFixedThreadPool(8);
try {
    Future<Result> future = pool.submit(() -> compute(input));
    Result result = future.get(30, TimeUnit.SECONDS);
} finally {
    pool.shutdown();
    pool.awaitTermination(30, TimeUnit.SECONDS);
}
```

`ExecutorService` (`Executors.newFixedThreadPool`, `newCachedThreadPool`, `newSingleThreadExecutor`) or `CompletableFuture.supplyAsync`/`runAsync` for asynchronous work. Provides lifecycle management, thread reuse, exception handling, and task queuing.

### Explicit Executor Shutdown

Call `shutdown()` followed by `awaitTermination()` in finally blocks. Leaked executors hold threads indefinitely, preventing JVM shutdown and consuming resources. Register shutdown hooks for long-lived executor pools.

### CompletableFuture for Async Composition

```java
CompletableFuture<OrderConfirmation> pipeline = userService.findUser(userId)
    .thenCompose(user -> orderService.create(user, request))
    .thenCombine(inventoryService.reserve(request), this::merge)
    .exceptionally(this::handleFailure);
```

Chain with `thenApply` (transform), `thenCompose` (chain dependent async), `thenCombine` (combine two futures), `exceptionally`/`handle` (recover). **Do not block with `.get()` or `.join()` in async code paths** — defeats the purpose and risks thread starvation.

### Thread-Safe Collections

```java
ConcurrentHashMap<String, Counter> counters = new ConcurrentHashMap<>();
counters.computeIfAbsent(key, k -> new Counter()).increment();   // atomic
```

Use `java.util.concurrent` collections: `ConcurrentHashMap`, `CopyOnWriteArrayList`, `BlockingQueue` implementations. `ConcurrentHashMap`'s `compute`/`computeIfAbsent`/`merge` are atomic — eliminates the check-then-act race.

### Shared Mutable State Discipline

Make shared mutable state either:

1. **Immutable** — records, unmodifiable collections.
2. **Thread-confined** — `ThreadLocal`, stack-local variables.
3. **Properly synchronized** — concurrent collections, atomic variables, locks.

Shared mutable state without synchronization is a data race. The JVM memory model does not guarantee visibility of writes across threads without a happens-before relationship. `volatile`, `synchronized`, atomic operations, and concurrent collections establish happens-before.

### Atomics

Use `AtomicInteger`, `AtomicLong`, `AtomicReference`, `LongAdder` for simple shared counters and references. Atomic operations are lock-free and outperform `synchronized` blocks for single-variable updates. `LongAdder` outperforms `AtomicLong` under high contention for counter-only use cases.

---
[Back to Overview](./OVERVIEW.md)
