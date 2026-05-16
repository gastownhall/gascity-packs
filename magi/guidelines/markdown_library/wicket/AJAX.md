# AJAX and Behaviors

### Ajax Components

| Component | Use |
|:----------|:----|
| `AjaxLink` | Triggers Ajax callback instead of full page reload |
| `AjaxButton` | Submits form via Ajax |
| `AjaxFallbackLink` | Graceful degradation if JavaScript is disabled |

Each receives `AjaxRequestTarget` for specifying components to re-render and JavaScript to execute.

### Ajax Behaviors

Behaviors add functionality to existing components without subclassing.

| Behavior | Use |
|:---------|:----|
| `AjaxFormComponentUpdatingBehavior` | Updates model on client event |
| `AjaxEventBehavior` | Responds to arbitrary DOM events |
| `OnChangeAjaxBehavior` | Specializes for change events |

Use throttling via `ThrottlingSettings` for rapid events like keystrokes.

### AjaxRequestTarget

The target collects:

- Components to re-render via `add()`.
- JavaScript to execute via `appendJavaScript()` and `prependJavaScript()`.
- Focus targets via `focusComponent()`.

**Components must have `setOutputMarkupId(true)` to be Ajax-updatable.** Use `setOutputMarkupPlaceholderTag(true)` for components that toggle visibility via Ajax — this maintains the placeholder when invisible.

---
[Back to Overview](./OVERVIEW.md)
