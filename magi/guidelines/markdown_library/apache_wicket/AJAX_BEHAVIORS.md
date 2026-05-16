# AJAX and Behaviors

### Ajax Components

| Component | Purpose |
|:----------|:--------|
| `AjaxLink<T>` | Triggers Ajax callback instead of full page reload |
| `AjaxButton` | Submits form via Ajax |
| `AjaxFallbackLink<T>` | Provides graceful degradation if JavaScript is disabled |

Each receives an `AjaxRequestTarget` for specifying components to re-render and JavaScript to execute.

### Ajax Behaviors

Behaviors add functionality to existing components without subclassing:

- `AjaxFormComponentUpdatingBehavior` — updates model on client event
- `AjaxEventBehavior` — responds to arbitrary DOM events
- `OnChangeAjaxBehavior` — specializes for change events

Use throttling via `ThrottlingSettings` for rapid events like keystrokes.

### AjaxRequestTarget

The target collects components to re-render via `add()`, JavaScript to execute via `appendJavaScript()` and `prependJavaScript()`, and focus targets via `focusComponent()`.

**Any component updated via Ajax must have `setOutputMarkupId(true)`. Components that toggle visibility via Ajax need `setOutputMarkupPlaceholderTag(true)` to maintain the placeholder when invisible.**

```java
AjaxLink<Void> refresh = new AjaxLink<>("refreshLink") {
    @Override
    public void onClick(AjaxRequestTarget target) {
        target.add(dataPanel);
        target.appendJavaScript("console.log('refreshed');");
    }
};
dataPanel.setOutputMarkupId(true);
add(refresh, dataPanel);
```

---
[Back to Overview](./OVERVIEW.md)
