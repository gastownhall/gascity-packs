# Components (1.5+)

### Component Architecture

The `.component()` API is mandatory for all view-level constructs with templates. It enforces isolated scope, `controllerAs: '$ctrl'`, and `bindToController: true`.

```javascript
angular.module('app.features.orders').component('orderList', {
    templateUrl: 'app/features/orders/order-list.html',
    controller: OrderListController,
    controllerAs: 'vm',
    bindings: {
        customerId: '<',
        onOrderSelect: '&'
    }
});
```

### Binding Types

- **`<` (one-way)**: Data flows down. Component must NOT mutate input.
- **`@` (interpolated string)**: Receives static or interpolated text.
- **`&` (callback)**: Child invokes to communicate with parent.
- **`=` (two-way)**: **Restrict to form controls.** Use `<` and `&` for all other data flow.

### Lifecycle Hooks

- **`$onInit()`**: Logic that depends on bindings. Replaces constructor setup.
- **`$onChanges(changes)`**: React to input changes. Replaces `$scope.$watch`.
- **`$onDestroy()`**: Cleanup (listeners, timers, intervals).
- **`$postLink()`**: DOM manipulation after rendering.

### Communication Patterns

- **Parent to child**: One-way bindings (`<`).
- **Child to parent**: Callback bindings (`&`).
- **Siblings**: Via shared parent or shared service.
- **Deep nesting**: Via injectable services.

---
[Back to Overview](./OVERVIEW.md)
