# Security Practices

### Template Security

Angular sanitizes values bound to templates by default. Never bypass sanitization without justification. `DomSanitizer.bypassSecurityTrustHtml()` and similar methods are potential XSS vectors and require security review.

### Content Security Policy (CSP)

- Prohibit inline scripts.
- Restrict style sources.
- Use nonce-based allowlisting for Angular runtime scripts in SSR.

### Authentication and Authorization

- Store tokens in HTTP-only cookies or memory (avoid `localStorage`).
- Implement route guards on protected routes.
- Proactively refresh tokens before expiration.
- Clear sensitive state on logout.

### CSRF Protection

Enable with `withXsrfConfiguration()` in `provideHttpClient()`. Ensure the backend sets the CSRF cookie and validates the header on state-changing requests.

### Input Validation

Validate at the form level (UX) and API level (enforcement). Sanitize user content before rendering, especially with `innerHTML` or dynamic URLs.

### Dependency Auditing

Run `npm audit` in CI. Block deployments with critical vulnerabilities. Stay within one major version of the latest Angular release to receive security patches.

---
[Back to Overview](./OVERVIEW.md)
