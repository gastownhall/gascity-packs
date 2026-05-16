# Memory Management

### ARC Fundamentals

| Reference | Use |
|:----------|:----|
| Strong (default) | Normal ownership |
| `weak var` | Delegates, observers, back-references in parent-child relationships |
| `unowned let` | Only when the referenced object is **guaranteed** to outlive the reference holder |

**Prefer `weak` over `unowned`** when lifetime guarantees are uncertain; the performance difference is negligible.

### Capture Lists

- Always specify capture semantics explicitly in closures that escape or are stored.
- Use `[weak self]` for closures stored as properties or passed to async APIs.
- Use `[unowned self]` only in closures where `self` provably outlives the closure.
- Capture specific values `[count = self.count]` when you need a snapshot rather than a live reference.

```swift
networkManager.fetch { [weak self] result in
    guard let self else { return }
    self.processResult(result)
}
```

### Common Retain Cycle Patterns

Cycles occur when:

- A closure stored on `self` captures `self` strongly.
- Two objects hold strong references to each other (delegate patterns without `weak`).
- Closures passed to long-lived operations (timers, notification observers) capture `self`.

Break cycles by:

- Using `[weak self]` and early-returning with `guard let self else { return }`.
- Marking delegate properties as `weak`.
- Invalidating timers and removing observers in `deinit`.

### Deinit Verification

- Implement `deinit` with a log statement during development to verify deallocation.
- Remove logging `deinit` implementations before release or gate behind a debug flag.
- **If `deinit` never fires, you have a retain cycle. Find it.**

---
[Back to Overview](./OVERVIEW.md)
