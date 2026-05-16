# Reactive Patterns and RxJS

### RxJS Scope

RxJS is reserved for asynchronous streams and complex temporal operations:
- HTTP request orchestration (retry, debounce, switchMap).
- WebSocket and Server-Sent Event streams.
- Race conditions and cancellation.
- Backpressure handling (throttle, audit, sample).

**RxJS is forbidden as a substitute for synchronous state management—use Signals.**

### Operator Selection

- **switchMap**: Cancels previous inner observable. Use for search-as-you-type or route param changes.
- **concatMap**: Queues inner observables sequentially. Use for ordered operations (form submissions).
- **mergeMap**: Runs inner observables concurrently. Use for fire-and-forget (logging).
- **exhaustMap**: Ignores new outer values while inner is active. Use for preventing duplicate clicks (login buttons).

### Subscription Management

Every subscription must have a termination strategy:
- **`async` pipe**: Preferred for templates. Auto-unsubscribes.
- **`toSignal()`**: Converts observable to signal. Manages lifecycle automatically in injection context.
- **`takeUntilDestroyed()`**: Completes observable when enclosing context is destroyed.
- **Manual `Subscription`**: Last resort. Call `unsubscribe()` in cleanup.

**Unmanaged subscriptions are forbidden — every leak is a memory bug.**

### Error Handling in Streams

Errors in RxJS streams are terminal. Use `catchError` to intercept and return recovery observables. Place `catchError` inside the inner observable of flattening operators to keep the outer stream alive.

```typescript
searchResults$ = this.searchTerm$.pipe(
    debounceTime(300),
    switchMap(term => this.searchService.search(term).pipe(
        catchError(() => of([])),
    )),
);
```

### Interop with Signals

- `toSignal()`: Bridge observable to signal at boundary points.
- `toObservable()`: Bridge signal to observable.

Avoid ping-ponging between signals and observables within the same operation.

---
[Back to Overview](./OVERVIEW.md)
