# Routing

`yew-router` provides SPA navigation with a `Routable` enum.

```rust
use yew::prelude::*;
use yew_router::prelude::*;

#[derive(Routable, PartialEq, Eq, Clone, Debug)]
pub enum Route {
    #[at("/")]
    Home,
    #[at("/users/:id")]
    User { id: u64 },
    #[at("/admin/*path")]
    Admin { path: String },
    #[not_found]
    #[at("/404")]
    NotFound,
}

fn switch(route: Route) -> Html {
    match route {
        Route::Home => html! { <HomePage /> },
        Route::User { id } => html! { <UserPage {id} /> },
        Route::Admin { path } => html! { <AdminPanel {path} /> },
        Route::NotFound => html! { <NotFound /> },
    }
}

#[function_component(App)]
pub fn app() -> Html {
    html! {
        <BrowserRouter>
            <Switch<Route> render={switch} />
        </BrowserRouter>
    }
}
```

### Navigation

```rust
use yew_router::prelude::*;

html! {
    <Link<Route> to={Route::User { id: 42 }}>
        {"View User"}
    </Link<Route>>
}

// Programmatic navigation
let navigator = use_navigator().expect("Navigator must be inside BrowserRouter");
navigator.push(&Route::Home);
```

### Rules

- **Always configure a `NotFound` route**; configure server SPA fallback to `index.html`.
- Use `Link` for client-side navigation; **avoid full reloads**.

---
[Back to Overview](./OVERVIEW.md)
