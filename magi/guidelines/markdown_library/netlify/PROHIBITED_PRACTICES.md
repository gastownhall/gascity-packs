# Prohibited Practices

### Never Do

- Commit secrets to `netlify.toml` — API keys, tokens, and passwords go in the UI with appropriate scoping. A secret in version control is shared with everyone who has repository access, every fork, and every CI log.
- Rely on UI-only configuration for reproducible builds — if someone forks the repository, they must be able to deploy an identical site from `netlify.toml` alone. UI settings with no `netlify.toml` equivalent must be documented in `DEPLOYMENT.md` or equivalent.
- Use `force = true` on redirects without understanding the consequence — forced redirects apply even when a file exists at the from path, overwriting static files with redirect responses. Silent failure that is difficult to diagnose.
- Mutate the container filesystem at runtime — serverless and edge functions run in ephemeral environments; files written during one invocation do not persist. Use Blobs or DB.
- Skip deploy previews for production-bound changes — saves five minutes and risks five hours of incident response.
- Leave Node.js versions unpinned — the platform's default version changes without notice.
- Deploy branch deploys for every branch — feature branches get deploy previews via PRs; branch deploys are for long-lived integration branches. Deploying every branch wastes build minutes and creates URL sprawl.
- Add CORS headers to edge functions or static assets unless explicitly required — misconfigured CORS creates security vulnerabilities. Proxy rewrites eliminate CORS entirely for same-origin API patterns.
- Use Blobs as a high-frequency write store — Blobs are optimized for frequent reads and infrequent writes. High write throughput degrades performance and can hit rate limits.
- Ignore the `Cache-Status` header when debugging performance — the header tells you exactly what the CDN did with your request.
- Promote a deploy to production without running shakedown against its preview URL.
- Run shakedown against `localhost` via `netlify dev` instead of the published preview URL.

---
[Back to Overview](./OVERVIEW.md)
