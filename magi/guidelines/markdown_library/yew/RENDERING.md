# Rendering and Templates

Use the `html!` macro sparsely; minimize dynamic allocations and conversions.

- Use `classes!` macro or simple class strings; **avoid building `String`s in render unless necessary**.
- Prefer inline conditionals for simple branches; break out into small components for complex branches.
- Keep inner closures small; **move heavy logic to helpers outside render**.

```rust
html! { { if condition { html!{{ "A" }} } else { html!{{ "B" }} } } }
```

---
[Back to Overview](./OVERVIEW.md)
