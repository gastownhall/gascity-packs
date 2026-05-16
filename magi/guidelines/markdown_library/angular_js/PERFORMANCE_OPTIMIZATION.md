# Performance Optimization

### Watcher Budget

Set an explicit watcher budget for the application:
- **Optimal**: < 1,000
- **Acceptable**: < 2,000
- **Critical**: 2,500+ (sluggish)

### One-Time Bindings

Apply `{{ ::value }}` to every binding that will not change during the component's lifetime. High-impact optimization.

### Required Production Optimizations

```javascript
angular.module('app').config(['$compileProvider', '$httpProvider', function($compileProvider, $httpProvider) {
    $compileProvider.debugInfoEnabled(false); // Saves memory
    $compileProvider.commentDirectivesEnabled(false);
    $compileProvider.cssClassDirectivesEnabled(false);
    $httpProvider.useApplyAsync(true); // Batches digest cycles
}]);
```

### Collection Size Boundaries

- **> 100 items**: Server-side pagination required.
- **> 500 items**: Virtual scrolling required.

### Avoid Deep Object Watching

`$scope.$watch(..., true)` is O(n) on every digest. Use `$watchCollection` or `$onChanges` instead. Reserve deep watching for small, bounded structures only.

---
[Back to Overview](./OVERVIEW.md)
