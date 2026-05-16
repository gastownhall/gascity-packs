# Security Practices

### Strict Contextual Escaping (SCE)

AngularJS sanitizes template values via `$sce`. **Never disable SCE** (`$sceProvider.enabled(false)`) — this opens XSS vectors.

### Trusted Content

Mark trusted content (e.g., from CMS) explicitly in a service via `$sce.trustAsHtml()`. Add security review comments explaining the trust.

### Expression Sandbox Removal

AngularJS 1.6+ has NO expression sandbox. **Never interpolate user input into templates or use `$compile` on user-supplied markup.**

### Content Security Policy (CSP)

Configure strict CSP headers. Use `ng-csp` on the root element if `unsafe-eval` is restricted.

### Dependency Pinning and Auditing

Audit for known vulnerabilities regularly. **Pin all dependency versions explicitly.** Avoid patch-level updates without review for end-of-life libraries.

---
[Back to Overview](./OVERVIEW.md)
