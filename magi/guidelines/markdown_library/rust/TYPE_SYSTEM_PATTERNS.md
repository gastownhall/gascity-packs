# Type System Patterns

### Newtype Pattern
Wrap primitive types for type safety:
```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct UserId(pub u64);

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Email(String);
impl Email {
    pub fn new(s: impl Into<String>) -> Result<Self, ValidationError> {
        let s = s.into();
        if s.contains('@') { Ok(Self(s)) } else { Err(ValidationError::InvalidEmail) }
    }
}
```

### Trait Bounds
```rust
fn process<T: Debug + Clone + Send + 'static>(item: T) { /* ... */ }
fn process<T>(item: T) where T: Debug + Clone + Send + 'static { /* ... */ }  // When bounds are long
async fn fetch<T: DeserializeOwned>(url: &str) -> Result<T, Error> { /* ... */ }
```

### Associated Types vs Generics
```rust
// Associated type: one implementation per type
trait Iterator { type Item; fn next(&mut self) -> Option<Self::Item>; }
// Generic: multiple implementations per type
trait From<T> { fn from(value: T) -> Self; }
```

---
[Back to Overview](./OVERVIEW.md)
