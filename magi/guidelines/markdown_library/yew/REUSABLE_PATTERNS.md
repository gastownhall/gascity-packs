# Reusable Patterns

### Data Fetching Hook

```rust
pub fn use_fetch<T>(url: String) -> LoadState<T>
where
    T: 'static + Clone + for<'de> Deserialize<'de>,
{
    let state = use_state(|| LoadState::Idle);
    {
        let state = state.clone();
        use_effect_with(url.clone(), move |url| {
            let state = state.clone();
            spawn_local(async move {
                state.set(LoadState::Loading);
                match fetch_json::<T>(&url).await {
                    Ok(data) => state.set(LoadState::Loaded(data)),
                    Err(e) => state.set(LoadState::Error(e.to_string())),
                }
            });
            || ()
        });
    }
    (*state).clone()
}
```

### Form Handling

```rust
use std::collections::HashMap;

#[derive(Clone, PartialEq, Default)]
struct FormData {
    username: String,
    email: String,
    errors: HashMap<String, String>,
}

#[function_component(Form)]
pub fn form() -> Html {
    let form = use_reducer(FormData::default);
    let onsubmit = {
        let form = form.clone();
        Callback::from(move |e: SubmitEvent| {
            e.prevent_default();
            let mut errors = HashMap::new();
            if form.username.is_empty() {
                errors.insert("username".to_string(), "Required".to_string());
            }
            if errors.is_empty() {
                spawn_local(async move {
                    // API call
                });
            } else {
                form.dispatch(FormAction::SetErrors(errors));
            }
        })
    };
    html! { /* form UI */ }
}
```

---
[Back to Overview](./OVERVIEW.md)
