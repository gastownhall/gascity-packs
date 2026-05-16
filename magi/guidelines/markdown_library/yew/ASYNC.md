# Async, Effects, and Data Fetching

Side effects belong in `use_effect` or spawned tasks; **never in render**. For async fetch, use `spawn_local` with an owned state handle.

```rust
use yew::prelude::*;
use serde::Deserialize;
use gloo_net::http::Request;
use wasm_bindgen_futures::spawn_local;

#[derive(Deserialize, Clone, PartialEq, Debug)]
struct Health { status: String }

async fn load_health() -> Result<Health, String> {
    Request::get("/api/health")
        .send()
        .await
        .map_err(|e| e.to_string())?
        .json::<Health>()
        .await
        .map_err(|e| e.to_string())
}

#[function_component(HealthView)]
pub fn health_view() -> Html {
    let data = use_state(|| Option::<Health>::None);
    let err = use_state(|| Option::<String>::None);
    let loading = use_state(|| false);
    {
        let data = data.clone();
        let err = err.clone();
        let loading = loading.clone();
        use_effect_with((), move |_| {
            spawn_local(async move {
                loading.set(true);
                match load_health().await {
                    Ok(h) => { data.set(Some(h)); err.set(None); },
                    Err(e) => { data.set(None); err.set(Some(e)); }
                }
                loading.set(false);
            });
            || ()
        });
    }
    html! {
        <div>
            if *loading { <p>{"Loading..."}</p> }
            else if let Some(e) = &*err { <p style="color:#b00;">{format!("Error: {}", e)}</p> }
            else if let Some(h) = &*data { <pre>{format!("status: {}", h.status)}</pre> }
            else { <p>{"No data"}</p> }
        </div>
    }
}
```

### spawn_local Pattern

```rust
use wasm_bindgen_futures::spawn_local;

spawn_local(async move {
    match fetch_data().await {
        Ok(data) => state.set(Some(data)),
        Err(e) => error.set(Some(e.to_string())),
    }
});
```

### Stream Handling

```rust
use futures::StreamExt;

spawn_local(async move {
    let mut stream = get_stream().await;
    while let Some(item) = stream.next().await {
        // Process item
    }
});
```

### Rules

- `use_effect_with(deps, f)` when effect depends on values; **deps must implement `PartialEq`**.
- **Clean up subscriptions in the effect's return closure.**
- **Do not block; use async and `spawn_local`.**

---
[Back to Overview](./OVERVIEW.md)
