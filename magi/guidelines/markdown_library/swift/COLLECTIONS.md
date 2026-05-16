# Collections and Functional Patterns

### Collection Choice

| Type | Properties |
|:-----|:-----------|
| Array | Ordered, indexed access, allows duplicates |
| Set | Unordered, unique elements, O(1) membership testing |
| Dictionary | Key-value pairs, O(1) lookup by key |
| `ContiguousArray` | When element type is a class and you need guaranteed contiguous storage |

### Functional Transformations

- Use `map`, `filter`, `reduce`, `compactMap`, `flatMap` for declarative transformations.
- Chain operations when readable; break into intermediate variables when chains exceed three operations.
- Prefer `lazy` for chained operations on large collections to avoid intermediate allocations.
- **Prefer `reduce(into:)` with mutation** over `reduce` for building collections — more efficient.

### Iteration

- Use `for-in` for simple iteration; clearer than `forEach`.
- Use `forEach` only when passing a method reference directly: `items.forEach(process)`.
- Use `enumerated()` when you need both index and element.
- Use `zip` to iterate two sequences in lockstep.

### Slicing and Subsequences

- Slice with ranges: `array[1..<4]`.
- **Slices share storage** with the original; copy explicitly if you need independence.
- Use `prefix`, `suffix`, `dropFirst`, `dropLast` for common slice patterns.

---
[Back to Overview](./OVERVIEW.md)
