# Component Architecture

### Component Hierarchy

| Class | Purpose |
|:------|:--------|
| `WebPage` | Top-level container representing a complete HTML page |
| `Panel` | Reusable component with its own markup file; use for any UI fragment reused across pages |
| `Fragment` | Inline markup reuse within a single HTML file via `wicket:fragment` tags |
| `Border` | Wraps child markup with surrounding decoration |
| `WebMarkupContainer` | Generic container for grouping or attaching behaviors |

### Component Lifecycle

Components progress through:

```text
Construction → onInitialize → onConfigure → onBeforeRender → Render → onAfterRender → onDetach
```

- **`onInitialize`** — Add all child components here. The component is fully integrated into the hierarchy at this point. Call `super.onInitialize()` first.
- **`onConfigure`** — Set visibility and enabled state here. Called every render cycle. **Never add or remove components in `onConfigure`.**
- **`onBeforeRender`** — Last chance to mutate the tree before rendering. Use sparingly.
- **`onDetach`** — Release expensive resources. Always call `super.onDetach()` last to ensure proper propagation to child components.

### Standard Component Pattern

```java
public class OrderSummaryPanel extends Panel {

    private final IModel<Order> orderModel;

    public OrderSummaryPanel(String id, IModel<Order> orderModel) {
        super(id, orderModel);
        this.orderModel = orderModel;
    }

    @Override
    protected void onInitialize() {
        super.onInitialize();
        add(new Label("orderNumber", new PropertyModel<>(orderModel, "number")));
        add(new Label("total", new PropertyModel<>(orderModel, "total")));
        add(new ListView<>("items", new PropertyModel<>(orderModel, "items")) {
            @Override
            protected void populateItem(ListItem<OrderItem> item) {
                item.add(new Label("name", new PropertyModel<>(item.getModel(), "name")));
            }
        });
    }

    @Override
    protected void onConfigure() {
        super.onConfigure();
        setVisible(orderModel.getObject() != null);
    }
}
```

### Markup Inheritance

Wicket supports markup inheritance parallel to Java class inheritance. Base page defines structure with `<wicket:child/>` placeholder; child pages provide content via `<wicket:extend>` tags. The rendered output merges base and child markup seamlessly. Use for consistent layouts across page hierarchies.

---
[Back to Overview](./OVERVIEW.md)
