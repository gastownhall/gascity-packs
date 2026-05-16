# Dependency Injection

### Minification-Safe Annotation Is Mandatory

JavaScript minifiers rename parameters, which destroys AngularJS's reflective DI. Every construct MUST declare dependencies using annotation-safe patterns.

**`$inject` property annotation** (preferred):
```javascript
OrderListController.$inject = ['OrderService', '$state'];
function OrderListController(OrderService, $state) {
    // ...
}
```

**Inline array annotation** (acceptable):
```javascript
angular.module('app').controller('OrderController',
    ['OrderService', '$state', function(OrderService, $state) { ... }]
);
```

**Implicit injection is prohibited** — it breaks in production after minification.

### `ng-strict-di` at Bootstrap

Enable the `ng-strict-di` attribute on the bootstrap element so implicit dependencies throw errors during development:

```html
<html ng-app="app" ng-strict-di>
```

---
[Back to Overview](./OVERVIEW.md)
