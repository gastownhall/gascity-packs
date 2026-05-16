# Resources and Header Contributions

### Package Resources

Resources (CSS, JavaScript, images) bundle with components in the same package. Reference via `PackageResourceReference`. Components contribute to the page head via `renderHead()` using `IHeaderResponse`.

### Header Contributions

Override `renderHead(IHeaderResponse)` to contribute resources:

```java
@Override
public void renderHead(IHeaderResponse response) {
    super.renderHead(response);
    response.render(CssHeaderItem.forReference(new PackageResourceReference(MyPanel.class, "MyPanel.css")));
    response.render(JavaScriptHeaderItem.forReference(new PackageResourceReference(MyPanel.class, "MyPanel.js")));
    response.render(OnDomReadyHeaderItem.forScript("initMyPanel('" + getMarkupId() + "');"));
}
```

| Header item | Purpose |
|:------------|:--------|
| `CssHeaderItem` | External CSS reference |
| `JavaScriptHeaderItem` | External JS reference |
| `CssContentHeaderItem` | Inline CSS |
| `OnDomReadyHeaderItem` | DOM-ready script |

Contributions deduplicate automatically — the same resource referenced by multiple components renders once.

### Resource Bundles

Bundle multiple resources for efficient loading via `getResourceBundles().addCssBundle()` and `addJavaScriptBundle()`. Bundled resources combine into a single request in production mode.

---
[Back to Overview](./OVERVIEW.md)
