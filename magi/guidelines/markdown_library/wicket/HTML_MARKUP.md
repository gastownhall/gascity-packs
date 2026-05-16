# HTML Markup

### Wicket Namespace Declaration

All Wicket templates **must** declare the Wicket namespace:

```html
<html xmlns:wicket="http://wicket.apache.org">
```

Components bind to elements via the `wicket:id` attribute. **The attribute value must exactly match the component ID in Java code.**

### Wicket Tags

| Tag | Purpose |
|:----|:--------|
| `wicket:panel` | Defines `Panel` root markup |
| `wicket:extend` | Provides child content in markup inheritance |
| `wicket:child` | Placeholder for child content in parent templates |
| `wicket:container` | Invisible grouping without HTML output |
| `wicket:enclosure` | Conditionally renders block based on child visibility |
| `wicket:message` | Inline internationalized text |
| `wicket:fragment` | Defines inline reusable markup |

### Template Best Practices

- Preserve valid HTML — templates must be previewable in browsers.
- Include meaningful placeholder text and structure for designer preview.
- Use CSS classes for styling, **never style based on `wicket:id` attributes**.
- Keep templates focused on structure; all logic belongs in Java code.

---
[Back to Overview](./OVERVIEW.md)
