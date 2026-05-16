# Events and Callbacks

Use closures or `use_callback` to create stable handlers. **Avoid recreating handlers every render when they capture stable deps.**

```rust
use yew::prelude::*;
use web_sys::HtmlInputElement;

#[function_component(SearchBox)]
pub fn search_box() -> Html {
    let query = use_state(|| AttrValue::from(""));
    let oninput = {
        let query = query.clone();
        use_callback(query, move |e: InputEvent, q| {
            let input: HtmlInputElement = e.target_unchecked_into();
            q.set(AttrValue::from(input.value()));
        })
    };
    html! { <input type="text" value={(*query).clone()} oninput={oninput} placeholder="Search..." /> }
}
```

### Rules

- Prefer `use_callback(deps, f)` to keep handler identity stable, aiding child memoization.
- Use `target_unchecked_into` for inputs when the event target is known; **avoid runtime panics by ensuring correct element types**.
- **Do not perform async work inline in event closures**; spawn tasks with `spawn_local`.

---
[Back to Overview](./OVERVIEW.md)
