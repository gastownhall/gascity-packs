# Nitro Server Routes

### Server Route Structure

Nitro server routes live in `server/api/` (for API endpoints) and `server/routes/` (for non-API server routes like webhooks or OAuth callbacks). File naming determines the HTTP method and path:

| File | Route |
|:-----|:------|
| `server/api/users.get.ts` | `GET /api/users` |
| `server/api/users.post.ts` | `POST /api/users` |
| `server/api/users/[id].get.ts` | `GET /api/users/:id` |

Use `defineEventHandler` to define route handlers. Handlers receive an H3 event object for request/response access.

### Input Validation

**Validate all input at the server route boundary.** Use `readBody(event)` for POST/PUT/PATCH bodies, `getQuery(event)` for query parameters, and `getRouterParam(event, 'id')` for route parameters. Validate with zod, valibot, or a similar runtime schema validator. Return a 400 response with structured error details for validation failures. **Never trust client-provided data — server routes are API endpoints exposed to the network.**

**Every server route that reads request body, query parameters, or route parameters validates input against a schema before processing.** Unvalidated input in server routes is the same vulnerability class as unsanitized SQL parameters.

### Server Utilities

Shared server logic lives in `server/utils/`. Nitro auto-imports from this directory. Place database clients, auth helpers, validation schemas, and shared response formatters here. Server utils are server-only code — they never ship to the client bundle. Use this for secrets access, database connections, and third-party API clients that require server-side credentials.

### Server Middleware

Nitro server middleware (`server/middleware/`) runs before every server route. Use for authentication verification, request logging, CORS headers, and rate limiting. Middleware handlers can modify the event context (`event.context.auth = user`) for downstream routes to consume. Order of execution follows alphabetical file naming. **Keep middleware focused and fast** — every millisecond in middleware adds to every request.

### Server Error Handling

Throw errors with `createError({ statusCode: 404, statusMessage: 'Not Found', data: { detail: '...' } })` for HTTP error responses. Nuxt converts these into proper HTTP responses with the correct status code. Unhandled exceptions in server routes return 500 with a generic message in production (no stack traces, no internal details). Log the full error server-side with context (route, parameters, user identity) for debugging. Define a global error handler in `server/plugins/` for centralized error logging and monitoring integration.

### Server Route Caching

Cache server route responses via `routeRules` in `nuxt.config.ts` or via the `defineCachedEventHandler` wrapper. Set cache TTL based on data freshness requirements. Use stale-while-revalidate for content that tolerates brief staleness. Cache keys incorporate the full request URL including query parameters by default. For personalized responses, vary the cache key by auth state or user segment, or disable caching entirely for per-user data.

### Database Integration

Database clients initialize in `server/utils/` or `server/plugins/`. Use connection pooling. Close connections gracefully on server shutdown via Nitro lifecycle hooks. **Never expose database credentials to the client** — they exist only in server-side code and runtime config (`runtimeConfig`, not `runtimeConfig.public`). ORM usage (Drizzle, Prisma, Kysely) follows the ORM's recommended patterns for serverless/edge environments: connection pooling adapters, prepared statements, and transaction management appropriate to the deployment target.

---
[Back to Overview](./OVERVIEW.md)
