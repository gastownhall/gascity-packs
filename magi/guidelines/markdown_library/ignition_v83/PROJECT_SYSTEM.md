# Project System (ResourceCollection)

### Project → ResourceCollection

| 8.1 | 8.3 |
|:----|:----|
| `Project` references | `ResourceCollection` |
| `com.inductiveautomation.ignition.common.project.ProjectManifest.getTitle()` | `com.inductiveautomation.ignition.common.resourcecollection.ResourceCollectionManifest.title()` |
| `ImageManager` (legacy) | Refactored to use 8.3 resource-based configuration storage |

### Resource.getData()

Signature changed: returns `Optional<ImmutableBytes>` instead of `@Nullable byte[]`.

```java
resource.getData("file.txt").ifPresent(bytes -> {
    byte[] raw = bytes.toByteArray();
    // process raw
});
```

### Project Injection (Immutable Projects)

```java
context.getProjectManager().addImmutableProject(
    ProjectFileUtil.importFromZip(stream, "MyDashboard"));
```

| Characteristic | Behavior |
|:---------------|:---------|
| Editable | No |
| Renameable / duplicable / exportable | No |
| Openable in Designer | No |
| Included in Gateway backups | No |
| Replicated by redundancy sync | No |
| Use cases | Module-bundled dashboards, reference configurations, ship-with-module customizations |

### Removed Methods (Project System)

- `GatewayModuleHook.initializeResourceTypeAdapterRegistry(ResourceTypeAdapterRegistry)`
- `ResourceUtil.getValidResourceName()`

---
[Back to Overview](./OVERVIEW.md)
