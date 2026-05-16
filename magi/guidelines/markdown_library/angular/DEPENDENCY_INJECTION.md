# Dependency Injection and Service Architecture

### The DI Hierarchy

**Root level** (`providedIn: 'root'`): Singleton across the application. Use for stateful services, HTTP, auth, and config.

**Route level** (`providers` array in route): Instance scoped to the route subtree. Destroyed when navigating away. Use for feature-specific state that should reset on navigation.

**Component level** (`providers` array in component): Instance per component instance. Use for component-specific state managers or mediator services.

### The `inject()` Function

Prefer the functional `inject()` API over constructor injection:

```typescript
export class OrderService {
    private readonly http = inject(HttpClient);
    private readonly config = inject(APP_CONFIG);
}

export const guard: CanActivateFn = () => inject(AuthService).isAuthenticated();
```

`inject()` works in constructors, field initializers, functional guards, resolvers, interceptors, and factory functions.

### Injection Tokens

Use `InjectionToken` for non-class dependencies:
```typescript
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL');
```

### Service Design Principles

**Single Responsibility**: A service does one thing. If a service name requires "and", split it.

**Stateless by Default**: Prefer stateless services. When state is required, manage it through Signals or state management with clear ownership.

**Explicit Dependencies**: Declare all dependencies through `inject()`. No global state access.

**Testability**: Every service is testable in isolation by providing mock dependencies through DI.

### `DestroyRef` and Cleanup

`DestroyRef` replaces manual `ngOnDestroy` for subscription cleanup:

```typescript
export class OrderListComponent {
    private readonly destroyRef = inject(DestroyRef);

    constructor() {
        this.updates$.pipe(
            takeUntilDestroyed(this.destroyRef),
        ).subscribe(update => this.handleUpdate(update));
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
