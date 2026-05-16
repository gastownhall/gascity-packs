# Interop (wasm-bindgen / web-sys)

- Use `web_sys` types for DOM interop; cast with `target_unchecked_into` when certain.
- For JS glue, declare `extern` blocks with `#[wasm_bindgen]` and **keep boundary thin**.

### Window Alert

```rust
use yew::prelude::*;
use wasm_bindgen::prelude::*;

#[wasm_bindgen(inline_js = "export function notify(s){ alert(s); }")]
extern "C" {
    pub fn notify(s: &str);
}

#[function_component(Alert)]
pub fn alert() -> Html {
    let onclick = Callback::from(|_| notify("Hello from Rust"));
    html! { <button onclick={onclick}>{"Alert"}</button> }
}
```

### JS Bindings

```rust
use wasm_bindgen::prelude::*;
use web_sys::{HtmlElement, Window};

#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(js_namespace = console)]
    fn log(s: &str);
    #[wasm_bindgen(js_namespace = ["window", "analytics"])]
    fn track(event: &str, properties: JsValue);
}

#[wasm_bindgen(inline_js = "
export function get_local_storage(key) {
    return window.localStorage.getItem(key);
}
export function set_local_storage(key, value) {
    window.localStorage.setItem(key, value);
}
")]
extern "C" {
    fn get_local_storage(key: &str) -> Option<String>;
    fn set_local_storage(key: &str, value: &str);
}
```

### Safe DOM Access

```rust
use web_sys::{HtmlInputElement, EventTarget};
use wasm_bindgen::JsCast;

// Safe cast with error handling
fn get_input_value(e: Event) -> Result<String, String> {
    e.target()
        .ok_or_else(|| "No target".to_string())?
        .dyn_into::<HtmlInputElement>()
        .map_err(|_| "Not an input element".to_string())
        .map(|input| input.value())
}

// Unchecked cast when type is guaranteed
fn handle_input(e: InputEvent) {
    let input: HtmlInputElement = e.target_unchecked_into();
    let value = input.value();
}
```

### Rules

- **Keep JS interop minimal and audited.**
- **Never block; all JS interop should be async/event-driven.**

---
[Back to Overview](./OVERVIEW.md)
