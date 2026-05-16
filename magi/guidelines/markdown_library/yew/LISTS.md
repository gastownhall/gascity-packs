# Lists, Keys, and Conditional Rendering

**Keys are essential for list diffing.** Use stable identifiers.

```rust
use yew::prelude::*;

#[derive(Clone, PartialEq)]
struct Item {
    id: u64,
    name: AttrValue,
}

#[function_component(ItemList)]
pub fn item_list() -> Html {
    let items = vec![
        Item { id: 1, name: "Alpha".into() },
        Item { id: 2, name: "Beta".into() },
        Item { id: 3, name: "Gamma".into() },
    ];
    html! { <ul>{ for items.into_iter().map(|it| html!{ <li key={it.id}>{it.name}</li> }) }</ul> }
}
```

### Rules

- `key` must be **unique and stable across renders**; prefer numeric IDs or unique strings.
- **Avoid using indices as keys** unless the list is static.

---
[Back to Overview](./OVERVIEW.md)
