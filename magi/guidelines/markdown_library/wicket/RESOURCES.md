# Resources

### Package Resources

Resources (CSS, JavaScript, images) bundle with components in the same package. Reference via `PackageResourceReference`. Components contribute to page head via `renderHead()` method using `IHeaderResponse`.

### Header Contributions

Override `renderHead(IHeaderResponse)` to contribute:

| Item | Contributes |
|:-----|:------------|
| `CssHeaderItem` | CSS |
| `JavaScriptHeaderItem` | JavaScript |
| `CssContentHeaderItem` | Inline styles |
| `OnDomReadyHeaderItem` | DOM-ready scripts |

Contributions deduplicate automatically — same resource referenced by multiple components renders once.

### Resource Bundles

Bundle multiple resources for efficient loading via `getResourceBundles().addCssBundle()` and `addJavaScriptBundle()`. Bundled resources combine into single request in production mode.

---
[Back to Overview](./OVERVIEW.md)
