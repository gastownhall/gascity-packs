# Signals and Reactive State

### Signal Fundamentals

Signals are synchronous reactive primitives. They integrate with Angular's change detection for fine-grained updates.

- **`signal<T>(initialValue)`**: Writable signal. Update with `.set()` or `.update()`.
- **`computed<T>(() => expression)`**: Derived signal. Lazy and memoized. Recalculates only when dependencies change.
- **`linkedSignal<T>(() => expression)`**: Writable signal whose value is derived but can be overridden.
- **`effect(() => { ... })`**: Side-effect runner. Use for logging, sync to storage, or DOM interop.

### Signal Usage Patterns

**Component state**: Local UI state (toggles, filters) belongs in component-level signals.

**Derived state**: `computed()` signals replace complex `ngOnChanges` and getter-based derivations. Prefer `computed()` over getters—getters recalculate on every access; computed signals memoize.

**Service state**: Singleton services expose state through readonly signals with controlled mutation methods.

```typescript
@Injectable({ providedIn: 'root' })
export class CartService {
    private readonly itemsSignal = signal<CartItem[]>([]);
    readonly items = this.itemsSignal.asReadonly();
    readonly total = computed(() => this.itemsSignal().reduce(...));

    addItem(item: CartItem): void { this.itemsSignal.update(items => [...items, item]); }
}
```

**Writable signals are private. Public exposure is `.asReadonly()` only.**

### Effect Guardrails

Use effects sparingly—they break unidirectional data flow. Appropriate for logging, syncing to storage, or bridging to non-Angular DOM APIs. Inappropriate for updating other signals (use `computed()`) or triggering HTTP requests (use explicit methods).

### Signal vs Observable Decision Matrix

| Characteristic | Signal | Observable (RxJS) |
|:---------------|:-------|:-------------------|
| Synchronous state | Preferred | Overhead unnecessary |
| Async event streams | Not suitable | Designed for this |
| Current value access | Immediate via `()` | Requires latest value tracking |
| Template binding | Direct call in template | Requires `async` pipe or `toSignal()` |
| Temporal operations | Not supported | debounce, throttle, interval |
| Computed derivations | `computed()` (memoized) | `combineLatest` (manual) |

---
[Back to Overview](./OVERVIEW.md)
