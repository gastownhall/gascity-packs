# Concurrency and Async/Await

### Structured Concurrency

| Pattern | Use |
|:--------|:----|
| `async let` | Independent parallel operations with known scope |
| `TaskGroup` | Dynamic number of concurrent operations |
| `Task {}` | Unstructured concurrency only when structured is impossible |
| **Detached tasks** | **Forbidden** without explicit lifecycle management |

```swift
func fetchDashboard() async throws -> Dashboard {
    async let user = fetchUser()
    async let posts = fetchPosts()
    async let notifications = fetchNotifications()
    return try await Dashboard(
        user: user,
        posts: posts,
        notifications: notifications
    )
}
```

### Actor Isolation

- Use actors for mutable shared state — **non-negotiable**.
- Access actor-isolated state from outside with `await`.
- Use `nonisolated` for computed properties or methods that don't touch mutable state.
- Use `@MainActor` for UI-bound state and view models; **apply at the type level, not per-method**.

```swift
@MainActor
final class ViewModel: ObservableObject {
    @Published private(set) var state: ViewState
    nonisolated func formatText(_ text: String) -> String {
        // Pure function, doesn't touch state
        return text.uppercased()
    }
    func updateState() async {
        // Runs on MainActor
        state = await fetchData()
    }
}
```

### Sendable Conformance

- Value types composed entirely of Sendable fields are **implicitly Sendable**.
- Reference types require **explicit `Sendable` conformance** with `@unchecked Sendable` only when you've verified thread safety manually.
- Closures crossing isolation boundaries must be `@Sendable`; capture only Sendable values.
- **Fix Sendable warnings.** They exist because the compiler found a data race.

### Cancellation

- Check `Task.isCancelled` or call `Task.checkCancellation()` in long-running loops.
- Clean up resources before returning from a cancelled task.
- Propagate cancellation by **not catching `CancellationError`** unless you have recovery logic.

### Async Sequences

- Use `AsyncStream` or `AsyncThrowingStream` to bridge callback-based APIs to async/await.
- Prefer `for await` loops over manual iterator handling.
- Implement `AsyncSequence` for custom data sources; **do not expose raw continuations**.

```swift
func observeValues() -> AsyncStream<Int> {
    AsyncStream { continuation in
        let observer = NotificationCenter.default.addObserver(
            forName: .valueChanged,
            object: nil,
            queue: .main
        ) { notification in
            if let value = notification.object as? Int {
                continuation.yield(value)
            }
        }
        continuation.onTermination = { _ in
            NotificationCenter.default.removeObserver(observer)
        }
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
