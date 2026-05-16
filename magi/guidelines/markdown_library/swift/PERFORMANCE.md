# Performance Optimization

### Measurement First

- Profile with **Instruments** before optimizing; intuition is unreliable.
- Use Time Profiler for CPU, Allocations for memory, Leaks for retain cycles.
- Establish baseline measurements; verify improvements quantitatively.

### Allocation Strategies

- Prefer value types; they're stack-allocated when possible and avoid heap overhead.
- Use `reserveCapacity` for arrays and dictionaries when the size is known ahead.
- Avoid repeated string concatenation in loops; use `String.reserveCapacity` or build arrays and `joined()`.
- Use `ContiguousArray` for performance-critical collections of reference types.

### Copy-on-Write

- Swift collections **copy lazily**: assignment is O(1), mutation triggers copy on first write.
- Use `isKnownUniquelyReferenced` for custom CoW types.
- Avoid holding multiple references to mutable collections in hot paths.

### Reducing Dynamic Dispatch

- Mark classes as `final` when subclassing is not intended.
- Use `private` or `fileprivate` access control; the compiler can devirtualize inaccessible members.
- Enable Whole Module Optimization (`-whole-module-optimization`) for release builds.

---
[Back to Overview](./OVERVIEW.md)
