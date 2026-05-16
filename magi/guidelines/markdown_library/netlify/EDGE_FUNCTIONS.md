# Edge Functions

### Architecture

Edge functions run on **Deno** at CDN edge locations closest to the requesting user. They execute before the CDN serves a response, operating as middleware in the request chain.

| Limit | Value |
|:------|:------|
| CPU time per invocation | 50 ms (wall-clock can exceed while awaiting I/O) |
| Code size per deployment | 20 MB compressed |
| Memory per deployment | 512 MB |

**Use edge functions for:**

- Request/response transformation.
- Geolocation-based routing.
- Authentication checks.
- A/B testing and personalization.
- Header manipulation.
- Short-lived compute benefiting from geographic proximity.

**Forbidden in edge functions:**

- Database writes to regionally hosted databases — round-trip negates edge benefit.
- Heavy computation exceeding 50 ms CPU.
- Long-running processes.
- Workloads requiring full Node.js API compatibility unavailable in Deno.

### Declaration and Routing

Edge functions live in `netlify/edge-functions/` by default. Declare routing in `netlify.toml`. Multiple edge functions can execute on the same path **in declaration order**. Each function can pass the request downstream by calling `context.next()` or short-circuit by returning a `Response` directly.

```toml
[[edge_functions]]
  function = "auth-check"
  path = "/dashboard/*"

[[edge_functions]]
  function = "geo-redirect"
  path = "/*"
```

### Edge vs Serverless

Do not default to edge functions because they sound faster. A function that calls a database in `us-east-1` from an edge node in Tokyo adds transatlantic latency that a co-located serverless function in `us-east-1` avoids entirely.

| Use Edge When | Use Serverless When |
|:--------------|:--------------------|
| Latency is the primary concern | Compute duration exceeds 50 ms |
| Operation completes in under 50 ms CPU time | Function communicates with a regionally hosted database |
| Logic benefits from geographic distribution (geo-routing, personalization) | Workload requires Node.js-specific APIs unavailable in Deno |
| You need to modify the request/response before it reaches origin | Function performs background or async processing |

### Edge Caching

Edge function responses are not cached by default. Enable caching by setting appropriate cache control headers. Separate **CDN cache directives** (`Netlify-CDN-Cache-Control`) from **browser cache directives** (`Cache-Control`).

```typescript
export default async (request: Request, context: Context) => {
  const data = await fetchExpensiveData();
  return new Response(JSON.stringify(data), {
    headers: {
      "Content-Type": "application/json",
      "Netlify-CDN-Cache-Control": "public, s-maxage=3600, stale-while-revalidate=60",
      "Cache-Control": "public, max-age=0, must-revalidate",
    },
  });
};
```

The CDN caches aggressively; the browser revalidates frequently. This pattern gives instant invalidation via deploy while keeping CDN hit rates high.

---
[Back to Overview](./OVERVIEW.md)
