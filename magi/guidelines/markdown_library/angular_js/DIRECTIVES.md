# Directives

### Directive Purpose

Directives extend HTML with custom behavior. Post-1.5, components handle templates; directives handle attribute-level behavioral extensions (DOM manipulation, event handling).

### When to Use Directives vs Components

- **Components**: For UI elements with a template and data bindings.
- **Directives**: For behavioral extensions to existing elements (e.g., auto-focus, tooltip).

### Restrict Property

- `'E'` (element): Reserved for components.
- `'A'` (attribute): Default for behavioral directives.
- `'C'` (class) and `'M'` (comment): **Prohibited.**

### Link Function vs Controller

- **Link function**: For DOM manipulation and event binding.
- **Controller**: For exposing an API to child directives.

### Cleanup on Destruction

Cleanup all listeners, timers, and subscriptions on scope destruction:

```javascript
link: function(scope, element) {
    var timer = $interval(update, 1000);
    scope.$on('$destroy', function() {
        $interval.cancel(timer);
    });
}
```

---
[Back to Overview](./OVERVIEW.md)
