# Error Handling and UX States

**Never use `unwrap` / `expect` in app code.** Represent UX states explicitly: `idle`, `loading`, `loaded(T)`, `error(String)`.

```rust
#[derive(Clone, PartialEq)]
pub enum LoadState<T> {
    Idle,
    Loading,
    Loaded(T),
    Error(String),
}

impl<T> LoadState<T> {
    pub fn is_loading(&self) -> bool {
        matches!(self, Self::Loading)
    }
    pub fn as_loaded(&self) -> Option<&T> {
        match self {
            Self::Loaded(data) => Some(data),
            _ => None,
        }
    }
}

// Usage in component
let data: UseStateHandle<LoadState<Data>> = use_state(|| LoadState::Idle);
html! {
    match &*data {
        LoadState::Idle => html! { <p>{"Ready to load"}</p> },
        LoadState::Loading => html! { <Spinner /> },
        LoadState::Loaded(d) => html! { <DataView data={d.clone()} /> },
        LoadState::Error(e) => html! { <ErrorMessage msg={e.clone()} /> },
    }
}
```

### Error Boundaries

Implement error boundaries for fault isolation.

```rust
#[function_component(ErrorBoundary)]
pub fn error_boundary(props: &ChildrenProps) -> Html {
    let fallback = html! {
        <div class="error-boundary">
            <h2>{"Something went wrong"}</h2>
            <button onclick={Callback::from(|_| {
                if let Some(window) = web_sys::window() {
                    let _ = window.location().reload();
                }
            })}>
                {"Reload"}
            </button>
        </div>
    };
    html! {
        <Suspense fallback={fallback}>
            { for props.children.iter() }
        </Suspense>
    }
}
```

### Rules

- Decide on **one enum per view or per resource**; prefer enums over multiple `Option<bool>` flags.
- Map any error into `String` with `e.to_string()` for display.
- For structured errors, define a small error type; **keep it `no_std` friendly where possible**.

---
[Back to Overview](./OVERVIEW.md)
