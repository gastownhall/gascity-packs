# Required Practices

### Always Do

- Keep lines **under 220 chars**; prefer single-line functions and handlers.
- Use **trailing commas** in multi-line lists, match arms, props, imports.
- Derive `Properties` + `PartialEq` for props; use `AttrValue` for strings.
- Use `Rc` / `Arc` for large shared payloads passed as props.
- Drive UI from explicit load states; show loading/error/empty distinctly.
- Memoize derived values and stabilize callbacks with `use_memo` / `use_callback`.
- `spawn_local` for async operations.
- Map errors to UI states.
- **Cleanup in `use_effect` returns.**
- 404 route handling.
- Serve SPA with proper `index.html` fallback.
- Run shakedown against both debug and release profiles after every triggering change.
- Capture all required shakedown artifacts (console capture, result summary, issue list, environment snapshot).

---
[Back to Overview](./OVERVIEW.md)
