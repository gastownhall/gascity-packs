# Memory and Ownership

### Ownership Rules
- **Single owner** — every value has exactly one owner
- **Borrowing** — references borrow without ownership
- **Move semantics** — default for non-Copy types

### Reference Preference Order
1. `&T` — immutable reference (most preferred)
2. `&mut T` — mutable reference
3. `T` — ownership transfer
4. `Clone` — explicit copy (least preferred)

### String Handling
```rust
fn accepts_str(s: &str) { /* ... */ }                    // Accept borrowed
fn returns_owned() -> String { "result".to_string() }    // Return owned
fn into_string(s: impl Into<String>) -> String { s.into() }  // Flexible input
```

### Cow for Conditional Ownership
```rust
use std::borrow::Cow;
fn process(input: &str) -> Cow<str> {
    if needs_modification(input) { Cow::Owned(modify(input)) } else { Cow::Borrowed(input) }
}
```

### Interior Mutability
```rust
use std::cell::{Cell, RefCell};
use std::sync::{Arc, RwLock, Mutex};
let counter = Cell::new(0);                          // Single-threaded, Copy types
let data = RefCell::new(vec![]);                     // Single-threaded, runtime borrow checking
let shared = Arc::new(RwLock::new(State::new()));    // Multi-threaded, prefer over Mutex
```

### Lifetime Elision
Let compiler infer when possible; explicit only when required:
```rust
fn first_word(s: &str) -> &str { s.split_whitespace().next().unwrap_or("") }
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str { if x.len() > y.len() { x } else { y } }
```

---
[Back to Overview](./OVERVIEW.md)
