# Internationalization

### Resource Bundles

Wicket uses `.properties` files for localized strings. Place alongside component class files with locale suffix:

```
HomePage.properties        # default
HomePage_de.properties     # German
HomePage_fr.properties     # French
```

Resources resolve up the component hierarchy enabling override at any level.

### StringResourceModel

Access localized strings with parameter substitution:

```java
add(new Label("greeting", new StringResourceModel("greeting.message", this)
        .setParameters(new PropertyModel<>(userModel, "name"))));
```

Use `ResourceModel` for simple key lookup. Parameters support `PropertyModel` for dynamic values from model objects.

### Locale Selection

Set locale via `Session.setLocale()`. Determine initial locale from request headers, user preferences, or URL parameters. Changing locale requires a page refresh to reload localized resources.

---
[Back to Overview](./OVERVIEW.md)
