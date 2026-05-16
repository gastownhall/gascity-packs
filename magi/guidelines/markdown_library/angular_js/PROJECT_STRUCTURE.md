# Project Structure and Organization

### Directory Layout

Organize by feature, not by technical role. Feature directories are self-contained vertical slices:

```
src/
├── app/
│   ├── core/
│   │   ├── authentication/
│   │   ├── http-interceptors/
│   │   └── services/
│   ├── features/
│   │   ├── orders/
│   │   │   ├── orders.module.js
│   │   │   ├── order-list.component.js
│   │   │   └── order.service.js
│   │   └── dashboard/
│   ├── shared/
│   │   ├── components/
│   │   └── directives/
│   ├── app.module.js
│   └── app.routes.js
└── index.html
```

### File Naming Conventions

File names encode purpose and type unambiguously. One construct per file:

- Components: `order-list.component.js`
- Controllers (legacy): `order-list.controller.js`
- Services: `order.service.js`
- Directives: `sort-header.directive.js`
- Filters: `currency-format.filter.js`
- Modules: `orders.module.js`
- Templates: `order-list.html`

### Layer Responsibilities

**Core**: Application-wide singletons (auth, interceptors, error handling). Loaded once at bootstrap. Core never depends on features.

**Features**: Self-contained vertical slices. Each feature directory contains its module, components, services, and routes. Features never import other features.

**Shared**: Reusable presentational components, directives, and filters. No feature-specific business logic. Shared components accept data through bindings.

---
[Back to Overview](./OVERVIEW.md)
