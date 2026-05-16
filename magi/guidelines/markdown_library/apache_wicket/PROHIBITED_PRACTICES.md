# Prohibited Practices

### Never Do

- Pass entities directly to components instead of wrapping in models — creates serialization bloat and stale data
- Store database entities or large objects in session — store IDs and reload when needed
- Use `getModelObject()` in constructors — model may not be initialized; value becomes static
- Add components in `onConfigure()` — use `onInitialize()` for component hierarchy construction
- Ignore `NotSerializableException` — every serialization failure indicates a real bug affecting clustering and back-button
- Use `setEscapeModelStrings(false)` with user-provided content — creates XSS vulnerabilities
- Access component hierarchy from background threads — components are not thread-safe
- Store non-serializable objects as component fields without marking `transient`
- Capture outer-class references in anonymous `LoadableDetachableModel` implementations
- Use the default `CryptoMapper` password — configure per-session encryption keys
- Call `setResponsePage()` after throwing an exception — page redirect is lost
- Modify component tree during rendering — use `onConfigure()` for visibility, `onBeforeRender()` for dynamic children
- Create circular model dependencies — leads to stack overflow during detachment
- Use `ListView` for large datasets without pagination — use `DataView` with `IDataProvider`
- Store business logic in page classes — delegate to services injected via DI
- Instantiate services directly in components — always use `@SpringBean` or `@Inject`
- Skip CSRF protection in production
- Run shakedown against mocked Spring beans or in-memory page stores when production uses real ones

### Always Do

- Use `LoadableDetachableModel` for any data loaded from database or external service
- Call super methods (`onInitialize`, `onConfigure`, `onDetach`) at appropriate positions
- Set `outputMarkupId(true)` for any component updated via Ajax
- Use `outputMarkupPlaceholderTag(true)` for components that toggle visibility via Ajax
- Implement proper `equals`/`hashCode` for entities used in `DropDownChoice` and similar
- Configure CSRF protection in production (`ResourceIsolationRequestCycleListener` or properly configured `CryptoMapper`)
- Enable CSP headers via `getCspSettings()`
- Validate all form input server-side regardless of client-side validation
- Use `CompoundPropertyModel` or `PropertyModel` for form binding
- Provide meaningful `wicket:id` names that reflect component purpose
- Test pages and panels with `WicketTester`
- Use `@SpringBean` or `@Inject` for service dependencies; never instantiate services in components
- Configure proper error pages for production deployment
- Mark session `dirty()` when modifying session state for cluster replication
- Use resource bundles for all user-visible strings; support i18n from the start
- Run shakedown after every trigger condition in §16

---
[Back to Overview](./OVERVIEW.md)
