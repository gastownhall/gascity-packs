# Core Principles

- **Zero unwrap / expect in application code — no exceptions.** Never use `unwrap()` or `expect()` in production paths.
- **220 character hard line limit.** Maximum line length is 220 characters.
- **Horizontal density.** Prefer compact single-line expressions when readable.
- **Zero panics in production.** All errors must be handled gracefully — map to UI states, never panic in user-facing code.

```rust
// FORBIDDEN
let value = some_option.unwrap();
let data = result.expect("should work");

// CORRECT
let value = some_option.unwrap_or_default();
let data = result.map_err(|e| e.to_string())?;
if let Some(value) = some_option { /* use value */ }
```

### Compact First, Multi-line When Necessary

- Favor single-line component functions, props, and handlers when under 220 chars.
- Break lines for clarity only when necessary (complex generics, long HTML trees).

```rust
#[function_component(Hello)]
pub fn hello() -> Html { html! { <div>{"Hello"}</div> } }
```

---
[Back to Overview](./OVERVIEW.md)
