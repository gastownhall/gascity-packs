# Required Practices

### Always Do

- Use `LoadableDetachableModel` for any data loaded from database or external service.
- Call super methods (`onInitialize`, `onConfigure`, `onDetach`) at appropriate positions.
- Set `outputMarkupId(true)` for any component updated via Ajax.
- Use `outputMarkupPlaceholderTag(true)` for components that toggle visibility via Ajax.
- Implement proper `equals`/`hashCode` for entities used in `DropDownChoice` and similar.
- Configure CSRF protection in production (`ResourceIsolationRequestCycleListener` or `CryptoMapper`).
- Enable CSP headers via `getCspSettings()`.
- Validate all form input server-side regardless of client-side validation.
- Use `CompoundPropertyModel` or `PropertyModel` for form binding.
- Provide meaningful `wicket:id` names that reflect component purpose.
- Test pages and panels with `WicketTester`.
- Use `@SpringBean` or `@Inject` for service dependencies; **never instantiate services in components**.
- Configure proper error pages for production deployment.
- Mark session `dirty()` when modifying session state for cluster replication.
- Use resource bundles for all user-visible strings; **support i18n from the start**.
- Run page-flow shakedown after every triggering change against a real servlet container.
- Capture all required shakedown artifacts (execution log, result summary, issue list, environment snapshot).

---
[Back to Overview](./OVERVIEW.md)
