# Error Handling

### No Empty Catches

```typescript
// PROHIBITED
try { ... } catch (e) { }
```

Every caught error is **logged, re-thrown, or handled with an explicit recovery action**. Silent error swallowing is the most insidious bug pattern — the application continues in a corrupted state with no diagnostic trail.

### `unknown` in Catch Clauses

Type catch clause variables as `unknown` (the default in TypeScript 5.x with `useUnknownInCatchVariables`):

```typescript
try {
  // ...
} catch (error: unknown) {
  if (error instanceof HttpError) {
    // ...
  } else if (error instanceof Error) {
    logger.error({ err: error });
  } else {
    logger.error({ caught: String(error) });
  }
}
```

Do not assume caught values are `Error` instances — they can be strings, numbers, or any thrown value.

### React Error Boundaries

Use Error Boundaries (class components with `componentDidCatch`, or libraries like `react-error-boundary`) to catch rendering errors in component subtrees. Display fallback UI, log the error, and provide recovery (retry, navigate away). **Without Error Boundaries, a single component error crashes the entire application.**

### Structured HTTP Errors in Node.js

Return structured error responses with appropriate HTTP status codes, a machine-readable error code, and a human-readable message. **Never return stack traces or internal error details in production responses.** Log the full error server-side. Map internal errors to user-safe error responses at the controller/handler layer.

### Result Types for Expected Failures

```typescript
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };

async function parseConfig(input: string): Promise<Result<Config>> {
  try {
    return { ok: true, value: JSON.parse(input) };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e : new Error(String(e)) };
  }
}
```

Result types make failure **explicit in the return type signature**, forcing callers to handle both paths. Especially valuable for validation, parsing, and operations where failure is a normal outcome.

---
[Back to Overview](./OVERVIEW.md)
