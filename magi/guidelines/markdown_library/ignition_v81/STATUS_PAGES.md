# Status Pages and Homepage Panels

```java
public class MyStatusPanel extends AbstractNamedTab {

    public MyStatusPanel() {
        super("modulename", StatusCategories.MODULES, "MyModule.statusTab");
    }

    @Override
    public WebMarkupContainer getPanel(String panelId) {
        return new BasicReactPanel(panelId, "myReactComponent", initialProps);
    }

    @Override
    public Optional<String> getMountedResourceFolder() { return Optional.of("mounted"); }

    @Override
    public Optional<String> getMountPathAlias() { return Optional.of("modulealias"); }
}

// GatewayHook
@Override
public List<? extends INamedTab> getStatusPanels() {
    return List.of(new MyStatusPanel());
}
```

Mounted resources are served from `/res/<alias>/`.

---
[Back to Overview](./OVERVIEW.md)
