# Observability and Debugging

### Deploy Logs

Every build produces a deploy log accessible from the Netlify dashboard capturing full build output: dependency installation, build command output, function bundling, deploy summary. **For public repositories, deploy logs default to public visibility** — set to private if build output contains sensitive information.

### Function Logs

Serverless function logs are available in real time from the Netlify dashboard. Logs capture `console.log`, `console.error`, and uncaught exceptions. Log retention varies by plan.

For long-term storage, configure log drains to send function logs to an external observability platform (Datadog, Splunk, or equivalent). Edge function logs route through the same pipeline — use `context.log()` or standard console methods.

### Netlify Observability

The Observability extension (generally available on paid plans) surfaces request-level metrics, function execution data, and error patterns directly in the Netlify dashboard. Tracks:

- Request volume and latency by path.
- Function invocation counts and durations.
- Error rates by deploy.
- Performance regressions tied to specific commits.

Use it to detect issues immediately after deploy rather than waiting for user reports.

### Cache-Status Debugging

The `Cache-Status` response header reports how Netlify's caching infrastructure handled a request. **Inspect it in browser developer tools or via `curl -I`. Never ignore this header when debugging performance.**

```http
Cache-Status: "Netlify Edge"; hit
Cache-Status: "Netlify Edge"; miss
Cache-Status: "Netlify Edge"; fwd=stale
```

| Value | Meaning |
|:------|:--------|
| `hit` | Edge served a cached response |
| `miss` | Request went to the origin |
| `fwd=stale` | Stale response served while revalidation happens in the background |

---
[Back to Overview](./OVERVIEW.md)
