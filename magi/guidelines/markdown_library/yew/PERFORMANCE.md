# Performance and Memoization

### Key Rules

- **Memoize derived data with `use_memo`**; supply minimal deps.
- **Stabilize callbacks with `use_callback`** to avoid child rerenders.
- Prefer `AttrValue` for textual props; prefer `Rc` for large shared data.
- **Avoid string building in `html!` repeatedly**; compute once with `use_memo`.
- Avoid cloning in tight loops; iterate by reference when possible.

### Efficient Props

```rust
// BAD: Cloning String every render
let text = props.text.clone();

// GOOD: Use AttrValue
pub struct Props {
    pub text: AttrValue,  // Cheap to clone
}

// GOOD: Use Rc for large data
pub struct Props {
    pub data: Rc<Vec<Item>>,  // Cheap reference clone
}
```

### Memoized Filter

```rust
let filtered = {
    let items = items.clone();
    let q = query.clone();
    use_memo((items, q), |(items, q)| {
        items.iter().filter(|x| x.name.contains(&q[..])).cloned().collect::<Vec<_>>()
    })
};
```

```rust
let filtered_items = use_memo(
    (items.clone(), filter.clone()),
    |(items, filter)| {
        items.iter()
            .filter(|item| item.matches(filter))
            .cloned()
            .collect::<Vec<_>>()
    },
);
```

### Keyed List

```rust
html! {
    <ul>
        { for items.iter().map(|item| {
            html! {
                <li key={item.id}>
                    {&item.name}
                </li>
            }
        }) }
    </ul>
}
```

---
[Back to Overview](./OVERVIEW.md)
