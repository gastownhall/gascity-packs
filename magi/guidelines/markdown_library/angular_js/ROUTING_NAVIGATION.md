# Routing and Navigation

### `ui-router` Is Mandatory

AngularJS's built-in `ngRoute` is forbidden. `ui-router` supports nested states, named views, and state machine navigation.

### State Configuration

Define states with names, URLs, components, and resolves:

```javascript
$stateProvider
    .state('orders', {
        url: '/orders',
        component: 'orderList',
        resolve: {
            orders: function(OrderService) {
                return OrderService.getAll();
            }
        }
    });
```

### Resolve Strategy

Resolves prefetch data before activation. Navigation waits for completion. Long resolve times block navigation; consider lazy-loading expensive details within the component instead.

### State Naming and Hierarchy

State names use dot notation (e.g., `orders.detail`). Child states inherit parent resolves and URL segments. Abstract states serve as non-navigable parent containers.

### State Change Events

Handle `$stateChangeError` at the application level. Unhandled failures break navigation silently. ui-router 1.0+ transition hooks are preferred.

---
[Back to Overview](./OVERVIEW.md)
