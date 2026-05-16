# State Management

### State Complexity Spectrum

Match the solution to the complexity:

- **Component state**: Signal-based `signal()` within the component. UI concerns (toggles, pagination).
- **Service state**: Injectable services with private writable signals and public readonly signals. Shared state for related components (shopping cart).
- **Dedicated state management**: NgRx SignalStore, NgRx Store. Required for complex derived state, optimistic updates, undo/redo, or SSR hydration boundaries.

### NgRx SignalStore

For structured state management, NgRx SignalStore provides signal-based reactive stores:

```typescript
export const OrderStore = signalStore(
    { providedIn: 'root' },
    withState<OrderState>({ orders: [], loading: false }),
    withComputed(({ orders }) => ({
        activeOrders: computed(() => orders().filter(o => o.status === 'active')),
    })),
    withMethods((store, orderApi = inject(OrderApiService)) => ({
        loadOrders: rxMethod<void>(pipe(
            switchMap(() => orderApi.getOrders({}).pipe(
                tapResponse({
                    next: orders => patchState(store, { orders, loading: false }),
                    error: error => patchState(store, { error: error.message }),
                }),
            )),
        )),
    })),
);
```

### State Ownership Rules

Every piece of state has exactly one owner:
- URL state: Owned by the router.
- Server state: Owned by API services/state management.
- UI state: Owned by component or feature-level service.
- User session: Owned by `AuthService`.

Consumers observe state through readonly signals but never mutate directly. Ambiguous ownership creates race conditions and stale data.

---
[Back to Overview](./OVERVIEW.md)
