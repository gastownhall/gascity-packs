# Security

### Authentication

Implement authentication via session state and authorization strategy. Configure `IAuthorizationStrategy` in `Application.init()`. Check authentication in `isInstantiationAuthorized()` for page access. Configure unauthorized component listener to redirect to login page.

### Role-Based Authorization

| Mechanism | Use |
|:----------|:----|
| `@AuthorizeInstantiation` | Restrict page access by role |
| `@AuthorizeAction` | Component-level action restrictions |
| `IRoleCheckingStrategy` | Determine user roles |
| `MetaDataRoleAuthorizationStrategy` | Programmatic role configuration |

### CSRF Protection

Enable CSRF protection via `ResourceIsolationRequestCycleListener` for modern fetch-metadata-based protection. Alternatively use `CryptoMapper` with per-session keys (`KeyInSessionSunJceCryptFactory`). **Never use default `CryptoMapper` password in production.**

**Enable CSRF protection in all production deployments.** Use `ResourceIsolationRequestCycleListener` or properly configured `CryptoMapper` with per-session encryption keys.

### Content Security Policy

Wicket 9+ includes CSP support via `getCspSettings()`. Configure `strict()` for maximum protection or customize directives for specific requirements. **CSP headers prevent XSS and data injection attacks.**

### Output Encoding

Wicket automatically HTML-encodes `Label` output. For raw HTML rendering, explicitly opt-in with `setEscapeModelStrings(false)` — **use only for trusted content**. Validate all input server-side regardless of client-side validation.

**Never use `setEscapeModelStrings(false)` with user-provided content.** This creates XSS vulnerabilities. Raw HTML rendering is only for trusted, server-generated content.

---
[Back to Overview](./OVERVIEW.md)
