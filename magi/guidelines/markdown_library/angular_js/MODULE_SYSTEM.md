# Module System

### Module Declaration

Every feature and layer declares its own Angular module. The application module aggregates them:

```javascript
angular.module('app', [
    'app.core',
    'app.shared',
    'app.features.orders',
]);
```

### Module Naming

Use dot-delimited namespacing that mirrors directory structure (e.g., `app.features.orders`).

### Module Anti-Patterns

- **Single monolithic module**: One `app` module for everything. prevents isolation and complicates testing.
- **Module per file**: Too many modules with no organizational benefit.
- **Circular module dependencies**: Module A depends on B, B depends on A. These fail at injection time.

### Module Configuration Phases

- **Configuration phase** (`.config()`): Runs before instantiation. Only providers and constants are injectable. Use for routes and provider setup. Services are NOT available.
- **Run phase** (`.run()`): Runs after instantiation. Use for app initialization and auth checks.

---
[Back to Overview](./OVERVIEW.md)
