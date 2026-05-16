# Filters

### Filter Purpose

Filters transform displayed values in templates (dates, currency, text case) without modifying source data.

### Built-in Filters

Use `currency`, `date`, `filter`, `json`, `limitTo`, `lowercase`, `number`, `orderBy`, `uppercase` before building custom alternatives.

### Custom Filter Definition

Register as pure functions:

```javascript
angular.module('app.shared').filter('statusLabel', function() {
    var labels = { pending: 'Awaiting Approval' };
    return function(status) { return labels[status] || status; };
});
```

### Filter Performance

Filters execute on every digest cycle. **`ng-repeat` filtering is discouraged in production** — pre-filter in the controller to avoid creating watchers for every digest.

### Stateless Filters Only

Filters MUST be stateless and idempotent. **`$stateful = true` is prohibited** as it disables caching and destroys performance.

---
[Back to Overview](./OVERVIEW.md)
