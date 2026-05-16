# Environment Configuration

### Type-Safe Environment Variables

```typescript
import { z } from 'zod'

const envSchema = z.object({
  VITE_API_URL: z.string().url(),
  VITE_APP_ENV: z.enum(['development', 'staging', 'production']),
  VITE_SENTRY_DSN: z.string().optional(),
  VITE_GA_ID: z.string().optional()
})

export const env = envSchema.parse(import.meta.env)

// Usage
const apiUrl = env.VITE_API_URL
const isProd = env.VITE_APP_ENV === 'production'
```

Validate environment at boot time. A missing or malformed env var must fail fast at app startup, not at the first usage site.

---
[Back to Overview](./OVERVIEW.md)
