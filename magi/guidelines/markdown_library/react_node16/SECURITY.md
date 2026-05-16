# Security

Frontend security prevents XSS, sensitive data exposure, and dependency supply chain attacks.

### `dangerouslySetInnerHTML`

Never use `dangerouslySetInnerHTML` without sanitizing the HTML with **DOMPurify** or equivalent. React escapes string values in JSX by default, preventing XSS. `dangerouslySetInnerHTML` bypasses this protection. Any user-generated or API-provided HTML passed to `dangerouslySetInnerHTML` without sanitization is an XSS vulnerability.

### Secrets in Client Bundles

Do **not** store secrets (API keys, tokens, signing keys) in:

- Client-side code
- Environment variables prefixed with `NEXT_PUBLIC_` or `VITE_`
- Any file that ships to the browser

**Client bundles are public.** Use server-side proxies for authenticated API calls. Publishable keys (Stripe `pk_*`, analytics IDs) are designed for client exposure — server-side secrets are not.

### Dependency Audit in CI

Run `npm audit` or `yarn audit` in CI. **Fail the build on high/critical severity vulnerabilities.** Use Dependabot, Renovate, or Socket to automate dependency updates and supply chain security monitoring. Pin dependencies to exact versions in lockfiles. Review the lockfile diff in PRs — a changed lockfile without a corresponding `package.json` change is suspicious.

### Sanitize User Input in Special Contexts

Sanitize all user input rendered in the UI, even in React's JSX (which auto-escapes). User input bypasses React's default escaping in:

- `href` attributes — `javascript:` protocol
- `style` attributes — `expression()`, `url()` with user-controlled values
- SVG content

Validate URLs with a URL parser and reject non-`http`/`https` schemes.

---
[Back to Overview](./OVERVIEW.md)
