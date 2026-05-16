# Controllers

### Controller Role

Controllers bind data to templates and delegate user actions to services. They are thin coordination layers. If a controller exceeds 100 lines, move logic to a service.

### `controllerAs` Syntax Is Mandatory

The `$scope`-based pattern is legacy debt. `controllerAs` makes data ownership explicit and is required for component compatibility.

```javascript
angular.module('app.features.orders').component('orderList', {
    templateUrl: 'app/features/orders/order-list.html',
    controller: OrderListController,
    controllerAs: 'vm',
    bindings: { customerId: '<' },
});
```
The `vm` alias (view-model) is the standard. Templates reference `vm.property`.

### Bindable Members at the Top

Expose template-bound properties and methods at the top of the controller function:

```javascript
function OrderListController(OrderService) {
    var vm = this;
    vm.orders = [];
    vm.loadOrders = loadOrders;

    function loadOrders() { ... }
}
```

---
[Back to Overview](./OVERVIEW.md)
