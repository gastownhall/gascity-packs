# Serverless Functions

### Architecture

Netlify Functions run on AWS Lambda.

| Type | Limit |
|:-----|:------|
| Default execution timeout | 10 s (26 s on paid plans) |
| Background Functions | Up to 15 minutes; cannot return a synchronous response |
| Scheduled Functions | Cron-like; do **not** run on deploy previews or branch deploys |

Functions deploy from the configured functions directory (default `netlify/functions`). Each file or directory becomes individually addressable at `/.netlify/functions/{name}`. Framework-generated functions (SSR routes, API endpoints) deploy automatically through framework adapters.

### Function Format (v2)

Use the modern Netlify Functions format. v2 receives standard `Request` objects and returns standard `Response` objects, aligning with web platform APIs. Use the `config` export to control routing, scheduling, and method filtering. Use `path` to mount functions at custom URLs:

```typescript
import type { Context, Config } from "@netlify/functions";

export default async (request: Request, context: Context) => {
  const body = await request.json();
  return Response.json({ received: true, timestamp: Date.now() });
};

export const config: Config = {
  path: "/api/submit",
};
```

### Background Functions

Background functions return immediate `202 Accepted` and continue executing asynchronously for up to 15 minutes. Use for batch processing, email dispatch, webhook fan-out, report generation, media transcoding.

Name files with a `-background` suffix (`process-upload-background.ts`) or configure via `config` export. The caller receives no body and no completion signal — implement a polling endpoint or webhook callback if completion notification is required.

### Scheduled Functions

```typescript
export default async (request: Request) => {
  const { next_run } = await request.json();
  // Perform scheduled work
};

export const config: Config = {
  schedule: "@daily",
};
```

| Constraint | Detail |
|:-----------|:-------|
| Execution | Production site only — not on deploy previews or branch deploys |
| Granularity | Minimum 1 minute |
| Timeout | Same as standard functions; if work needs more, trigger a background function |
| Schedule | Standard cron syntax + shorthand aliases: `@hourly`, `@daily`, `@weekly` |

### Function Region

By default functions deploy to `us-east-1`. When a function communicates with a database or external API in a specific region, **co-locate the function in the same region** to minimize latency. Region selection lives in the UI/API, not in `netlify.toml`.

---
[Back to Overview](./OVERVIEW.md)
