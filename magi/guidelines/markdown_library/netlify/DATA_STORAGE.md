# Data and Storage Primitives

### Netlify Blobs

Key/value object store with zero configuration. Access from functions, edge functions, and build plugins. Optimized for frequent reads and infrequent writes.

| Aspect | Detail |
|:-------|:-------|
| Site-level stores | Persist across deploys |
| Deploy-scoped stores | Immutable after deploy completes — build plugins MUST write here to prevent failed deploys from corrupting production |
| Default consistency | Eventual; writes propagate globally within 60 s |
| Strong consistency | Opt in when immediate read-after-write correctness is required (slower reads) |

```typescript
import { getStore } from "@netlify/blobs";

export default async (request: Request, context: Context) => {
  const store = getStore("user-preferences");
  const prefs = await store.get("user-123", { type: "json" });
  return Response.json(prefs);
};
```

Blobs support arbitrary JSON metadata attached to each entry — store content types, timestamps, access control flags, or cache invalidation markers without deserializing the body.

### Netlify DB

Serverless Postgres via Neon. Connection credentials inject automatically into function environment variables. Suitable for relational data, transactional workloads, and applications that outgrow the key/value model.

| Status | Detail |
|:-------|:-------|
| Maturity | Beta — evaluate migration paths and backup strategies before committing production data |
| Cold starts | Neon scales to zero when idle — first query after inactivity has cold-start latency. Account for this in user-facing flows |

### Blobs vs DB

Each primitive exists for a reason — misapplying them creates performance problems the platform cannot optimize away.

| Use Blobs When | Use DB When |
|:---------------|:------------|
| Data is unstructured or semi-structured | Data requires relational integrity |
| Access patterns are simple key lookups | Queries involve joins or aggregations |
| Write frequency is low | Write frequency is high |
| Application benefits from edge-cached reads with eventual consistency | Application needs transactions |

---
[Back to Overview](./OVERVIEW.md)
