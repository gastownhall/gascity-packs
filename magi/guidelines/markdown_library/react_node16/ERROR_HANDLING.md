# Error Handling

React error boundaries catch rendering errors in the component tree. Combined with TypeScript's type system and TanStack Query's error handling, they form a comprehensive error handling strategy.

### Error Boundaries

Wrap major UI sections in error boundaries. An uncaught rendering error without an error boundary crashes the entire React application. Error boundaries catch errors in their child component tree and render a fallback UI. Use **`react-error-boundary`** for function-component-friendly error boundary with reset capabilities. Place boundaries around:

- Route-level content
- Independent widgets
- Third-party component integrations

### Beyond Error Boundaries

Error boundaries do **not** catch errors in event handlers, async code, or server-side rendering. Handle these with:

- `try/catch` in event handlers
- `.catch()` on promises
- TanStack Query's `onError` callbacks
- Global `window.onerror` / `unhandledrejection` listeners for unexpected errors

Report caught errors to an error tracking service (Sentry, Datadog, Bugsnag).

### Typed Errors

Type errors explicitly. Do **not** `catch (error)` and assume `error is Error`. In TypeScript, caught values are `unknown`. Narrow with `instanceof Error` checks or a type guard. TanStack Query's error generic: `useQuery<Data, ApiError>` types the `error` field. Create a typed error hierarchy for the application (`ApiError`, `ValidationError`, `NetworkError`) with discriminated union structure.

```typescript
try {
  await fetchUser();
} catch (error: unknown) {
  if (error instanceof ApiError) {
    // handle API error
  } else if (error instanceof Error) {
    // generic Error
  } else {
    // unknown thrown value
  }
}
```

---
[Back to Overview](./OVERVIEW.md)
