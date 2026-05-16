# Localization

`BundleUtil`-based localization. Required for all user-visible text.

```java
// Register (in setup or startup)
BundleUtil.get().addBundle("MyModule", getClass(), "MyModule");

// Lookup
String label  = BundleUtil.get().getString("MyModule.deviceCount");
String pretty = BundleUtil.get().getString("MyModule.deviceCount.with", count);

// Cleanup (in shutdown)
BundleUtil.get().removeBundle("MyModule");
```

| File | Purpose |
|:-----|:--------|
| `MyModule.properties` | Base (English) |
| `MyModule_es.properties` | Spanish |
| `MyModule_zh_CN.properties` | Simplified Chinese |

Locale-suffixed siblings auto-load when the user's locale matches.

---
[Back to Overview](./OVERVIEW.md)
