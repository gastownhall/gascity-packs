# Vision Components

Vision components are Swing JavaBeans with BeanInfo introspection. Scope `CD` (Client + Designer).

### Component Class Requirements

| Constraint | Detail |
|:-----------|:-------|
| Base class | Extend `AbstractVisionComponent`, `AbstractVisionPanel`, or `AbstractVisionScrollPane` (NOT raw Swing) |
| Constructor | Public no-arg constructor mandatory (palette instantiates via reflection) |
| Properties | JavaBean getter/setter pairs for every exposed property. **Setters MUST call `firePropertyChange(name, oldValue, newValue)` for binding propagation** |
| Lifecycle | `onStartup()` and `onShutdown()` — start/stop timers, subscribe/unsubscribe events |
| Locale | Override `localeChanged()` if the component renders locale-sensitive text |

### BeanInfo Class

```java
public class MyComponentBeanInfo extends CommonBeanInfo {

    public MyComponentBeanInfo() {
        super(MyComponent.class,
              DynamicPropertyProviderCustomizer.VALUE_DESCRIPTOR,
              StyleCustomizer.VALUE_DESCRIPTOR);
    }

    @Override
    protected void initProperties() throws IntrospectionException {
        super.initProperties();
        addProp("dataset", "Dataset", "The bound dataset",
                CAT_DATA, PREFERRED_MASK | BOUND_MASK);
        addProp("pollRate", "Poll Rate", "Update interval in milliseconds",
                CAT_BEHAVIOR, BOUND_MASK);
    }

    @Override
    public Image getIcon(int kind) {
        switch (kind) {
            case ICON_COLOR_16x16:
            case ICON_MONO_16x16:
                return loadImage("/images/mycomponent_16.png");
            case ICON_COLOR_32x32:
            case ICON_MONO_32x32:
                return loadImage("/images/mycomponent_32.png");
        }
        return null;
    }

    @Override
    protected void initDesc() {
        VisionBeanDescriptor d = getBeanDescriptor();
        d.setName("My Component");
        d.setDisplayName("My Component");
        d.setShortDescription("Custom data display component");
    }
}
```

| Property Mask | Effect |
|:--------------|:-------|
| `PREFERRED_MASK` | Show in main property table |
| `BOUND_MASK` | Allow expression bindings |
| `EXPERT_MASK` | Hide unless "Show Expert" enabled |
| `HIDDEN_MASK` | Never show in property table |
| `NOT_TRANSLATABLE_MASK` | Skip during string translation |

| Category | Use For |
|:---------|:--------|
| `CAT_DATA` | Datasets, query bindings |
| `CAT_APPEARANCE` | Colors, fonts, borders |
| `CAT_BEHAVIOR` | Poll rates, click handlers |
| `CAT_LAYOUT` | Position, size |
| `CAT_COMMON` | General-purpose |

### BeanInfo Search Path Registration

```java
// DesignerHook.startup
context.addBeanInfoSearchPath("com.company.module.beaninfos");
```

### Palette Registration

```java
// DesignerHook.startup
VisionDesignerInterface vision = context.getModule(VisionDesignerInterface.VISION_MODULE_ID);
PaletteController palette = vision.getPaletteController();
palette.addGroup("My Module")
       .addPaletteItem(new JavaBeanPaletteItem(MyComponent.class));
```

---
[Back to Overview](./OVERVIEW.md)
