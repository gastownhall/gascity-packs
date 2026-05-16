# Async Patterns

### `async`/`await` Over `.then`

```typescript
async function fetchUser(id: string): Promise<User> {
  const response = await fetch(`/api/users/${id}`);
  if (!response.ok) throw new HttpError(response.status);
  return UserSchema.parse(await response.json());
}
```

The explicit return type catches cases where the function accidentally returns the wrong type.

### `Promise.allSettled` vs `Promise.all`

| Use | When |
|:----|:-----|
| `Promise.allSettled` | Concurrent operations where individual failures should not abort the batch |
| `Promise.all` | All promises must succeed for the operation to be meaningful |

`Promise.all` rejects on the first failure, **losing the results of other settled promises**.

### `AbortController` for Cancellation

```typescript
const controller = new AbortController();
const data = await fetch(url, { signal: controller.signal });

// Cancel on component unmount
useEffect(() => {
  return () => controller.abort();
}, []);
```

Pass `AbortSignal` to `fetch`, database clients, custom async functions. Cancel on component unmount, route navigation, timeout. **Uncancelled requests consume server resources and may update stale UI state after the component has unmounted.**

### `Promise.withResolvers()` (ES2024 / Node 22+)

```typescript
const { promise, resolve, reject } = Promise.withResolvers<User>();
```

Replaces the awkward pattern of extracting `resolve`/`reject` from the `Promise` constructor callback into outer-scope variables.

---
[Back to Overview](./OVERVIEW.md)
