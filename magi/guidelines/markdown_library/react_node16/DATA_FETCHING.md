# Data Fetching

Data fetching is the interface between the frontend and the outside world. Every fetch boundary is a trust boundary that requires type validation, error handling, and loading state management.

### TanStack Query for Server State

Use TanStack Query (React Query) for **all** server-state data fetching: API calls, remote configuration, search results, paginated lists. TanStack Query provides:

- Automatic caching
- Background refetching
- Optimistic updates
- Pagination/infinite scroll support
- Request deduplication

**Do not implement manual `useEffect` + `useState` + `fetch` patterns for server data in new code.**

### Runtime Validation at the Fetch Boundary

Validate API responses at runtime with zod or valibot. TypeScript types evaporate at runtime — an API that returns `{ name: null }` when the type says `{ name: string }` produces a runtime error far from the fetch site. Parse the response **at the fetch boundary**:

```typescript
const user = UserSchema.parse(response.data);
```

This catches contract violations at the earliest possible point.

### Loading, Error, Empty States

Handle loading, error, and empty states in every component that consumes fetched data. TanStack Query's `isLoading`, `isError`, `error`, and `data` fields make this straightforward:

- A component that renders data without checking `isLoading` flickers or crashes on first render.
- A component that ignores `isError` silently hides API failures.

### Centralized API Client

Centralize API client configuration in a single module:

- Base URL from environment variables
- Default headers
- Authentication token injection
- Error interceptors
- Response transformation

Use a typed wrapper around `fetch` or `axios` that applies these defaults. Every API call goes through this client — **no one-off `fetch()` calls with hardcoded URLs scattered across components.**

### Request Cancellation

Implement request cancellation for fetches triggered by user input (search, autocomplete, filters). Use `AbortController` to cancel in-flight requests when the component unmounts or when new input supersedes the previous request. TanStack Query integrates with `AbortSignal` via the `queryFn`'s `signal` parameter. Uncancelled requests from unmounted components waste bandwidth and may trigger state-update-on-unmounted-component issues.

---
[Back to Overview](./OVERVIEW.md)
