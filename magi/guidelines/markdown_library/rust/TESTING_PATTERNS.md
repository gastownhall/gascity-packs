# Testing Patterns

### Test Module Structure
```rust
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_basic_functionality() { assert_eq!(function_under_test(input), expected); }
    #[test]
    fn test_edge_case() { assert!(function_under_test("").is_err()); }
}
```

### Async Tests
```rust
#[tokio::test]
async fn test_async_operation() { assert!(async_function().await.is_ok()); }

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn test_concurrent_operation() { /* ... */ }
```

### Test Naming Convention
```rust
fn function_name_condition_expected_result() { /* ... */ }
// Examples: parse_valid_json_returns_ok, parse_empty_string_returns_error
```

### Property-Based Testing
```rust
use proptest::prelude::*;
proptest! {
    #[test]
    fn test_roundtrip(s in "\\PC*") {
        let encoded = encode(&s);
        prop_assert_eq!(s, decode(&encoded)?);
    }
}
```

### Integration Tests
Place in `tests/` directory:
```rust
// tests/integration.rs
use my_crate::{Client, Config};
#[tokio::test]
async fn test_full_workflow() {
    let client = Client::new(Config::from_env().unwrap());
    assert!(client.execute_workflow().await.is_ok());
}
```

---
[Back to Overview](./OVERVIEW.md)
