# Security

### Authentication

Implement authentication via session state and an authorization strategy. Configure `IAuthorizationStrategy` in `Application.init()`. Check authentication in `isInstantiationAuthorized()` for page access. Configure an unauthorized-component listener to redirect to a login page.

### Role-Based Authorization

Use `@AuthorizeInstantiation` to restrict page access by role. Use `@AuthorizeAction` for component-level action restrictions. Implement `IRoleCheckingStrategy` to determine user roles. `MetaDataRoleAuthorizationStrategy` provides programmatic role configuration:

```java
@AuthorizeInstantiation("ADMIN")
public class AdminPage extends WebPage { /* ... */ }

@AuthorizeAction(action = Action.RENDER, roles = "MANAGER")
public class ManagerOnlyPanel extends Panel { /* ... */ }
```

### CSRF Protection

Enable CSRF protection in **all** production deployments. Two supported mechanisms:

- `ResourceIsolationRequestCycleListener` (modern, fetch-metadata based) — preferred.
- `CryptoMapper` with per-session keys via `KeyInSessionSunJceCryptFactory`.

**Never use the default `CryptoMapper` password in production** — configure per-session encryption keys.

```java
getRequestCycleListeners().add(new ResourceIsolationRequestCycleListener());
```

### Content Security Policy

Wicket 9+ includes CSP support via `getCspSettings()`. Configure `strict()` for maximum protection or customize directives for specific requirements. CSP headers prevent XSS and data-injection attacks:

```java
getCspSettings().blocking().strict();
```

### Output Encoding

Wicket automatically HTML-encodes `Label` output. For raw HTML rendering, explicitly opt-in with `setEscapeModelStrings(false)` — **only for trusted, server-generated content.**

**Never use `setEscapeModelStrings(false)` with user-provided content.** This creates XSS vulnerabilities. Raw HTML rendering is exclusively for trusted, server-generated content.

---
[Back to Overview](./OVERVIEW.md)
