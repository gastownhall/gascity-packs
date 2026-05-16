# Prohibited Practices

### Never Do

- Pass entities directly to components instead of wrapping in models. **Creates serialization bloat and stale data.**
- Store database entities or large objects in session. **Store IDs and reload when needed.**
- Use `getModelObject()` in constructors. Model may not be initialized; value becomes static.
- Add components in `onConfigure()`. Use `onInitialize()` for component hierarchy construction.
- Ignore `NotSerializableException`. **Every serialization failure indicates a real bug affecting clustering and back-button.**
- Use `setEscapeModelStrings(false)` with user-provided content. **Creates XSS vulnerabilities.**
- Access component hierarchy from background threads. **Components are not thread-safe.**
- Store non-serializable objects as component fields without marking transient.
- Capture outer class references in anonymous `LoadableDetachableModel` implementations.
- Use default `CryptoMapper` password. **Configure per-session encryption keys.**
- Call `setResponsePage()` after throwing exception. **Page redirect is lost.**
- Modify component tree during rendering. Use `onConfigure()` for visibility, `onBeforeRender()` for dynamic children.
- Create circular model dependencies. **Leads to stack overflow during detachment.**
- Use `ListView` for large datasets without pagination. Use `DataView` with `IDataProvider`.
- Store business logic in page classes. **Delegate to services injected via DI.**
- Skip page-flow shakedown after a triggering change.
- Run page-flow shakedown entirely inside `WicketTester` and declare success.
- Mock `@SpringBean` dependencies during shakedown — proxy resolution must run against real beans.

---
[Back to Overview](./OVERVIEW.md)
