# Props and Data Flow

Props drive component input and re-render triggers. **Derive `Properties` and `PartialEq` for diffing.**

```rust
use yew::prelude::*;
use std::rc::Rc;

#[derive(Properties, PartialEq, Clone)]
pub struct ComponentProps {
    pub label: AttrValue,           // Use AttrValue for strings
    #[prop_or_default]
    pub count: u32,                 // Use Copy types when possible
    #[prop_or(false)]
    pub active: bool,
    pub data: Rc<Data>,             // Use Rc for large shared data
}

#[derive(Properties, PartialEq, Clone)]
pub struct BadgeProps {
    pub label: AttrValue,
    #[prop_or(false)]
    pub important: bool,
}

#[function_component(Badge)]
pub fn badge(props: &BadgeProps) -> Html {
    let class = if props.important { "badge badge-important" } else { "badge" };
    html! { <span class={class}>{props.label.clone()}</span> }
}
```

### Rules

- Use **`AttrValue`** for string props (avoids unconditional heap clone).
- Use `Copy` types where possible (`bool`, `u32`).
- For large payloads, use **`Rc` or `Arc` inside props** to cheap-clone.
- Props must be `PartialEq` to allow Yew to skip rerenders; ensure only meaningful fields participate.

---
[Back to Overview](./OVERVIEW.md)
