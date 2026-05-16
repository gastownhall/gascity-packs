# State Management and Hooks

### Local State

| Hook | Use |
|:-----|:----|
| `use_state` | Small scalar values or `Rc` blobs |
| `use_reducer` | Structured state with actions (Redux-like pattern) |
| `use_memo` | Derived values; prevents expensive re-calculations on every render |
| `use_callback` | Stable closures; prevents unnecessary re-renders of child components |

### use_state

```rust
let counter = use_state(|| 0);
let increment = {
    let counter = counter.clone();
    Callback::from(move |_| counter.set(*counter + 1))
};
```

### use_reducer

```rust
use yew::prelude::*;
use std::rc::Rc;

#[derive(Clone, PartialEq)]
struct Counter { value: i32 }

enum Action { Inc, Dec, Reset }

fn reducer(state: Counter, action: Action) -> Counter {
    match action {
        Action::Inc => Counter { value: state.value + 1 },
        Action::Dec => Counter { value: state.value - 1 },
        Action::Reset => Counter { value: 0 },
    }
}

#[function_component(CounterView)]
pub fn counter_view() -> Html {
    let counter = use_reducer(|| Counter { value: 0 });
    let inc = { let counter = counter.clone(); Callback::from(move |_| counter.dispatch(Action::Inc)) };
    let dec = { let counter = counter.clone(); Callback::from(move |_| counter.dispatch(Action::Dec)) };
    let reset = { let counter = counter.clone(); Callback::from(move |_| counter.dispatch(Action::Reset)) };
    html! {
        <div>
            <button onclick={dec}>{"-"}</button>
            <span>{counter.value}</span>
            <button onclick={inc}>{"+"}</button>
            <button onclick={reset}>{"reset"}</button>
        </div>
    }
}
```

### use_effect with Cleanup

**Always return a cleanup closure.**

```rust
use_effect_with(deps, move |_| {
    let handle = setup_subscription();
    move || {
        handle.cleanup();
    }
});
```

### use_memo and use_callback

```rust
let expensive_value = use_memo(
    (input1, input2),
    |(i1, i2)| expensive_computation(i1, i2),
);

let onclick = use_callback(
    deps.clone(),
    move |_, deps| { /* handler */ },
);
```

### Custom Hooks

Extract reusable logic into custom hooks.

```rust
pub fn use_api<T: 'static + Clone>(url: &str) -> UseStateHandle<Option<T>> {
    let data = use_state(|| None);
    {
        let data = data.clone();
        let url = url.to_string();
        use_effect_with((), move |_| {
            spawn_local(async move {
                // Fetch logic
            });
            || ()
        });
    }
    data
}
```

### Global State / Context API

Yew's Context API allows components to publish a value (application state, theme, authentication status) and descendant components to consume it without prop-drilling.

```rust
use yew::prelude::*;
use std::rc::Rc;

// 1. Define your global state
#[derive(Debug, Clone, PartialEq)]
pub struct AppGlobalState {
    pub user_name: Option<AttrValue>,
    pub theme: AttrValue,
}

impl Default for AppGlobalState {
    fn default() -> Self {
        Self { user_name: None, theme: "light".into() }
    }
}

// 2. Define actions
pub enum AppGlobalAction {
    SetUserName(AttrValue),
    ToggleTheme,
}

// 3. Reducer
fn app_global_reducer(state: Rc<AppGlobalState>, action: AppGlobalAction) -> Rc<AppGlobalState> {
    match action {
        AppGlobalAction::SetUserName(name) => Rc::new(AppGlobalState { user_name: Some(name), ..(*state).clone() }),
        AppGlobalAction::ToggleTheme => Rc::new(AppGlobalState {
            theme: if state.theme == "light" { "dark".into() } else { "light".into() },
            ..(*state).clone()
        }),
    }
}

// 4. Provider
#[function_component(GlobalStateProvider)]
pub fn global_state_provider(props: &ChildrenProps) -> Html {
    let app_state_handle = use_reducer(AppGlobalState::default);
    html! {
        <ContextProvider<UseReducerHandle<AppGlobalState>> context={app_state_handle}>
            { for props.children.iter() }
        </ContextProvider<UseReducerHandle<AppGlobalState>>>
    }
}

// 5. Consumer
#[function_component(UserPanel)]
pub fn user_panel() -> Html {
    let app_state = use_context::<UseReducerHandle<AppGlobalState>>()
        .expect("No AppGlobalState context found. Did you forget GlobalStateProvider?");
    let toggle_theme = {
        let app_state = app_state.clone();
        Callback::from(move |_| app_state.dispatch(AppGlobalAction::ToggleTheme))
    };
    html! {
        <div class={format!("p-4 border {}", app_state.theme)}>
            if let Some(name) = &app_state.user_name {
                <p>{"Welcome, "}{name}{"!"}</p>
            } else {
                <p>{"Please log in."}</p>
            }
            <p>{"Current theme: "}{app_state.theme}</p>
            <button onclick={toggle_theme}>{"Toggle Theme"}</button>
        </div>
    }
}

#[function_component(App)]
pub fn app() -> Html {
    html! {
        <GlobalStateProvider>
            <UserPanel />
        </GlobalStateProvider>
    }
}
```

### Rules for Global State

- **Single Source of Truth** — Global state has a single owning component (`GlobalStateProvider`) that manages its creation and updates.
- **Minimal & Essential** — Only store truly global or frequently accessed data in context. **Avoid overusing context for localized component state.**
- **`Rc` for Sharing** — When sharing handles to state or reducers, `Rc` (or `Arc` for multi-threaded scenarios, less common in WASM UI) is essential for cheap cloning and shared ownership.
- **Define Actions** — For complex global state, use a reducer pattern (`use_reducer` with actions) for predictable state transitions.
- **Error Handling** — Use `expect` on `use_context` only if certain the provider is an ancestor. Otherwise, handle the `None` case gracefully (default value or specific error UI).

### Rules (All State Management)

- Keep state minimal; **derive from props when possible via `use_memo`**.
- **Do not keep duplicated state**; prefer single source of truth.
- Avoid cloning large data in render; **wrap in `Rc` and clone cheap handles**.

---
[Back to Overview](./OVERVIEW.md)
