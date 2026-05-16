# Project Architecture and Module Strategy

### Directory Structure

Organize by feature, not by technical role. Feature directories are self-contained vertical slices of functionality:

```
src/
├── app/
│   ├── core/
│   │   ├── interceptors/
│   │   ├── guards/
│   │   ├── services/
│   │   └── models/
│   ├── features/
│   │   ├── dashboard/
│   │   ├── orders/
│   │   └── settings/
│   ├── shared/
│   │   ├── components/
│   │   ├── directives/
│   │   ├── pipes/
│   │   └── utils/
│   ├── app.component.ts
│   ├── app.config.ts
│   └── app.routes.ts
├── environments/
├── styles/
└── assets/
```

### Layer Responsibilities

**Core**: Singleton services, HTTP interceptors, route guards, authentication, and application-wide models. Core services are `providedIn: 'root'`. Nothing in Core imports from Features.

**Features**: Self-contained vertical slices owning routes, components, feature-specific services, and models. Features may import from Shared but never from other Features. Cross-feature communication flows through Core services or state management.

**Shared**: Reusable presentational components, directives, pipes, and utility functions consumed across multiple features. Shared components are stateless or locally stateful—they never inject feature-specific services.

### NgModule Elimination

New applications use `bootstrapApplication()` with standalone components exclusively. The `app.config.ts` file replaces `AppModule`. NgModules remain only for consuming third-party libraries that have not migrated to standalone APIs.

### Lazy Loading Boundaries

Every feature directory defines its own route configuration returned via lazy-loaded `loadChildren` or `loadComponent`. The application route file contains only top-level paths with lazy references.

```typescript
// features/orders/orders.routes.ts
export const orderRoutes: Routes = [
    { path: '', component: OrderListComponent },
    { path: ':id', component: OrderDetailComponent },
];

// app.routes.ts
{ path: 'orders', loadChildren: () => import('./features/orders/orders.routes').then(m => m.orderRoutes) }
```

### Barrel Exports

Each feature and shared directory exposes a public API through an `index.ts` barrel file. Internal implementation files are not imported directly from outside the feature boundary.

---
[Back to Overview](./OVERVIEW.md)
