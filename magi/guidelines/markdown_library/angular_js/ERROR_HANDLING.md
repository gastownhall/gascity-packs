# Error Handling

### Promise Error Handling

Every promise chain must handle errors and finalization:

```javascript
OrderService.getAll()
    .then(...)
    .catch(function(error) {
        vm.error = error.message;
    })
    .finally(function() {
        vm.loading = false;
    });
```
**Empty `.catch()` blocks are prohibited.**

### State Change Errors

Handle `$stateChangeError` (or `$transitions.onError`) at the application level to avoid silent navigation failures.

### Loading and Error State Pattern

Every data-driven view explicitly accounts for loading, error, and success states in the template.

---
[Back to Overview](./OVERVIEW.md)
