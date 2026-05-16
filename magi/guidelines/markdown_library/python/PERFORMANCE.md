# Performance

### Never Optimize Without Measurement
- Profile before optimizing.
- Focus on algorithmic improvements first.

### Generators for Large Sequences
```python
def read_large_file(path: str) -> Iterator[str]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield line.strip()
```

### Caching Expensive Computations
Use `lru_cache` for expensive computations.

### Batch Processing
Use generators to process items in batches.

---
[Back to Overview](./OVERVIEW.md)
