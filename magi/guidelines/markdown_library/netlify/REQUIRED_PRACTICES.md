# Required Practices

### Always Do

- Pin runtime versions in `netlify.toml` for Node.js, Hugo, Ruby, Python, and Go.
- Declare redirects, headers, and routing in `netlify.toml` rather than the UI.
- Set security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, HSTS) on every production site.
- Use deploy previews as the primary verification step before merging to production.
- Scope environment variables to the minimum required context (Builds, Functions, or Runtime) and deploy context (production, preview, branch).
- Configure the `ignore` command for monorepos and projects where not every commit affects deployed output.
- Separate CDN cache headers from browser cache headers using `Netlify-CDN-Cache-Control` and `Cache-Control` independently.
- Test edge functions locally with `netlify dev` before deploying — edge function failures return 500 errors to users with no automatic fallback.
- Use deploy-scoped Blob stores for write operations in build plugins to prevent failed deploys from corrupting production data.
- Monitor usage metrics against plan limits monthly to prevent overage surprises or site pausing.
- Run a §5 shakedown after every change touching `netlify.toml`, `_redirects`, `_headers`, functions, edge functions, plugin declarations, env scopes, framework adapters, or runtime pins.

---
[Back to Overview](./OVERVIEW.md)
