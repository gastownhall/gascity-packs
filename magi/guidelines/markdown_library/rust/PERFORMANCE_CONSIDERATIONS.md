# Performance Considerations

### Allocation Avoidance
```rust
fn process(data: &[u8]) -> &[u8] { &data[..data.len().min(1024)] }  // No allocation
```

### Iterator Preference
```rust
// Good: lazy, no intermediate allocations
let sum: u64 = items.iter().filter(|x| x.is_valid()).map(|x| x.value()).sum();
```

### Capacity Pre-allocation
```rust
let mut results = Vec::with_capacity(items.len());
let mut map = HashMap::with_capacity(expected_size);
```

### Zero-Copy Parsing
```rust
#[derive(Deserialize)]
struct Data<'a> {
    #[serde(borrow)]
    name: &'a str,
}
```

---
[Back to Overview](./OVERVIEW.md)
