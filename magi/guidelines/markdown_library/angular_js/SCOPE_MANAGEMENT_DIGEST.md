# Scope Management and Digest Cycle

### The Digest Cycle

AngularJS uses dirty checking. Every watcher is evaluated on every digest cycle. Performance is proportional to watcher count.

### Scope Hierarchy

- Prototypal inheritance tree rooted at `$rootScope`.
- Component isolated scopes eliminate inheritance bugs by requiring explicit bindings.
- `$scope.$parent` and prototypal chains are **forbidden**.

### Minimizing Watchers

- **One-time bindings**: `{{ ::expression }}` deregisters after first evaluation.
- **`ng-if` over `ng-show`**: `ng-if` destroys scope and watchers; `ng-show` only hides.
- **Debounced `ng-model`**: Reduce cycles triggered by rapid input.
- **Track-by in `ng-repeat`**: Enables DOM node reuse; mandatory for mutable collections.
- **`$watchCollection` over deep `$watch`**: Deep watching large objects is **prohibited**.

### Digest Cycle Triggers

- Built-in directives and services trigger digests automatically.
- External events (3rd party libraries) require `$scope.$apply()` or `$scope.$applyAsync()`.
- **Never call `$apply()` inside a digest cycle.** Use `$applyAsync()` or `$timeout()` instead.

---
[Back to Overview](./OVERVIEW.md)
