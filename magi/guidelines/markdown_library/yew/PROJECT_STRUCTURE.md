# Project Structure

Predictable directory structure for UI crates.

```text
ui/
├── Cargo.toml
├── Trunk.toml
├── index.html
└── src/
    ├── main.rs
    ├── app.rs
    ├── routes.rs
    ├── api.rs
    ├── components/
    │   ├── mod.rs
    │   ├── header.rs
    │   ├── footer.rs
    │   └── [component].rs
    ├── pages/
    │   ├── mod.rs
    │   ├── home.rs
    │   └── [page].rs
    ├── state/
    │   ├── mod.rs
    │   ├── app_state.rs
    │   └── [state].rs
    ├── hooks/
    │   ├── mod.rs
    │   ├── use_api.rs
    │   └── [hook].rs
    ├── style/
    │   ├── tailwind.css
    │   └── [styles].css
    └── utils/
        ├── mod.rs
        └── [util].rs
```

### Rules

- **One component per file** by default; mark with `#[function_component(Name)]`. Exception: a parent and a small child component may share a file when tightly coupled.
- Modules grouped by role: `pages` (route targets), `components` (re-usable), `state` (reducers/contexts), `hooks` (custom hooks).
- **Shared types live in a separate `shared-types` crate** to avoid server-only deps.

---
[Back to Overview](./OVERVIEW.md)
