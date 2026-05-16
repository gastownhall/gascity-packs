# Routing and Navigation

### Route Configuration

Define routes as typed, flat arrays using functional APIs:

```typescript
export const routes: Routes = [
    { path: '', component: HomeComponent },
    {
        path: 'orders',
        loadChildren: () => import('./features/orders/orders.routes').then(m => m.orderRoutes),
        canActivate: [authGuard],
    },
    { path: '**', component: NotFoundComponent },
];
```

### Functional Guards

Replace class-based guards with functional equivalents:

```typescript
export const authGuard: CanActivateFn = () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    return auth.isAuthenticated() ? true : router.createUrlTree(['/login']);
};
```

### Resolvers

Functional resolvers prefetch data before route activation:

```typescript
export const orderResolver: ResolveFn<Order> = (route) => {
    const orderService = inject(OrderService);
    return orderService.getById(route.paramMap.get('id')!);
};
```

### Component Input Binding

Enable `withComponentInputBinding()` in router config to automatically bind route params, query params, and resolver data to component inputs:

```typescript
// Route: /orders/:id?status=active
export class OrderDetailComponent {
    id = input.required<string>();         // from :id
    status = input<string>();              // from ?status=
    order = input.required<Order>();       // from resolver
}
```

### Route-Level Providers

Scope services to route subtrees by attaching providers to route configurations. Services are instantiated when the route activates and destroyed when it deactivates. This creates natural state boundaries without global singletons.

### View Transitions

Enable with `withViewTransitions()` in router configuration for browser-native crossfade transitions between route changes. Customize with CSS `::view-transition`.

---
[Back to Overview](./OVERVIEW.md)
