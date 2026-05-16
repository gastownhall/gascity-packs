# Security

### `dangerouslySetInnerHTML`

```typescript
import DOMPurify from 'isomorphic-dompurify';

<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(content) }} />
```

If raw HTML must be rendered, **sanitize with DOMPurify or equivalent** before rendering. Unsanitized HTML enables XSS. React's JSX escapes text content by default — `dangerouslySetInnerHTML` bypasses this protection.

### Validate at the Server Boundary

Validate and sanitize **all external input** at the server boundary using zod, valibot, or io-ts:

```typescript
const CreateUserSchema = z.object({
  email: z.string().email(),
  displayName: z.string().min(1).max(100),
});

app.post('/users', async (req, res) => {
  const body = CreateUserSchema.parse(req.body);  // throws on invalid
  // ... body is fully typed and validated
});
```

The schema serves dual purpose: runtime validation and TypeScript type inference. **Unvalidated request bodies, query parameters, and URL parameters are untrusted regardless of the client that sent them.**

### Secrets in Environment Variables

**Never store secrets in environment variables prefixed with `NEXT_PUBLIC_`, `VITE_`, or `EXPO_PUBLIC_`.** These prefixes expose variables to the client bundle. Server-only secrets use **unprefixed environment variables** accessed only in server-side code.

### `yarn audit` in CI

Run `yarn audit` (or `yarn npm audit`) and address high/critical vulnerabilities. Integrate vulnerability scanning in CI. For vulnerabilities in transitive dependencies, use Yarn's `resolutions` field:

```json
{
  "resolutions": { "vulnerable-package": ">=2.0.1" }
}
```

### `helmet` for HTTP Security Headers

Use `helmet` (or equivalent) middleware for Node.js HTTP servers to set:

- `Content-Security-Policy`
- `Strict-Transport-Security`
- `X-Content-Type-Options`
- `X-Frame-Options`
- `Referrer-Policy`

These are the server-side complement to frontend security practices.

---
[Back to Overview](./OVERVIEW.md)
