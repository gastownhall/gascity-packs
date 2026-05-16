# Component Conventions

Function components exclusively. Bodies small and single-purpose.

```rust
use yew::prelude::*;

#[function_component(Hello)]
pub fn hello() -> Html {
    html! { <div>{"Hello, Yew"}</div> }
}

#[function_component(App)]
pub fn app() -> Html {
    html! { <main><Hello /></main> }
}

fn main() {
    console_error_panic_hook::set_once();
    wasm_logger::init(wasm_logger::Config::default());
    yew::Renderer::<App>::new().render();
}
```

### Rules

- One component per file by default; mark with `#[function_component(Name)]`.
- Return type is `Html`; keep simple return paths; avoid intermediate variables unless needed.
- **No side effects in render**; perform side effects in hooks (`use_effect`, `spawn_local`).

---
[Back to Overview](./OVERVIEW.md)
