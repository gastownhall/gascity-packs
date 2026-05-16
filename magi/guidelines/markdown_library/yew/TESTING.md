# Testing

| Target | Tool |
|:-------|:-----|
| Pure Rust logic (utils, reducers, formatters, parsers) | Standard `#[cfg(test)]` test runner |
| Browser components | `wasm-bindgen-test` (isolate small render checks only) |

### Unit Tests

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reducer() {
        let state = State { count: 0 };
        let new_state = reducer(Rc::new(state), Action::Increment);
        assert_eq!(new_state.count, 1);
    }

    #[test]
    fn test_format_date() {
        let date = format_date("2024-01-01");
        assert_eq!(date, "January 1, 2024");
    }

    #[test]
    fn reducer_inc_works() {
        let s = Counter { value: 1 };
        let s2 = reducer(s, Action::Inc);
        assert_eq!(s2.value, 2);
    }
}
```

### Browser Tests

```rust
#[cfg(test)]
mod tests {
    use wasm_bindgen_test::*;
    use yew::prelude::*;
    wasm_bindgen_test_configure!(run_in_browser);

    #[wasm_bindgen_test]
    async fn test_component_renders() {
        let rendered = yew::LocalServerRenderer::<App>::new()
            .render()
            .await;
        assert!(rendered.contains("expected text"));
    }
}
```

### Rules

- **Keep component tests minimal**; heavy DOM tests are slow and brittle.
- **Validate reducers, formatters, and parsers extensively.**
- Prefer extracting logic into testable functions.

---
[Back to Overview](./OVERVIEW.md)
