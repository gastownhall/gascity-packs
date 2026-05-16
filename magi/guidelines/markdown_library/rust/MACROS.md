# Macros

### Declarative Macros
```rust
macro_rules! hashmap {
    ($($key:expr => $value:expr),* $(,)?) => {{
        let mut map = std::collections::HashMap::new();
        $(map.insert($key, $value);)*
        map
    }};
}
let map = hashmap! { "a" => 1, "b" => 2 };
```

### Derive Macros
Prefer derive macros over manual implementations:
```rust
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Config { /* fields */ }
```

### Common Derives
- `Debug` — always include for debugging
- `Clone` — when copies are needed
- `PartialEq`, `Eq` — for equality comparison
- `Hash` — for HashSet/HashMap keys
- `Default` — when sensible defaults exist
- `Serialize`, `Deserialize` — for serialization

---
[Back to Overview](./OVERVIEW.md)
