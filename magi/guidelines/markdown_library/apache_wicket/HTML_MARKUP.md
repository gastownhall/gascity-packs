# HTML Markup

### Wicket Namespace Declaration

All Wicket templates must declare the Wicket namespace. Components bind to elements via the `wicket:id` attribute. The attribute value must exactly match the component ID in Java code:

```html
<!DOCTYPE html>
<html xmlns:wicket="http://wicket.apache.org">
<head>
    <title>Order Summary</title>
</head>
<body>
    <div wicket:id="orderSummary" class="card">
        <h2 wicket:id="orderNumber">Order #12345</h2>
        <p wicket:id="total">$0.00</p>
    </div>
</body>
</html>
```

### Wicket Tags

| Tag | Purpose |
|:----|:--------|
| `<wicket:panel>` | Defines Panel root markup |
| `<wicket:extend>` | Provides child content in markup inheritance |
| `<wicket:child/>` | Placeholder for child content in parent templates |
| `<wicket:container>` | Invisible grouping without HTML output |
| `<wicket:enclosure>` | Conditionally renders block based on child visibility |
| `<wicket:message>` | Inline internationalized text |
| `<wicket:fragment>` | Defines inline reusable markup |

### Template Best Practices

- Preserve valid HTML — templates must be previewable in browsers without Wicket processing.
- Include meaningful placeholder text and structure for designer preview.
- Use CSS classes for styling, **never** style based on `wicket:id` attributes (`wicket:id` is a binding contract, not a CSS hook).
- Keep templates focused on structure; all logic belongs in Java code.

---
[Back to Overview](./OVERVIEW.md)
