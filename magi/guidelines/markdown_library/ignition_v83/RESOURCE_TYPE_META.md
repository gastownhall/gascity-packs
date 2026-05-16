# ResourceTypeMeta

The declarative manifest controlling all platform integration of a resource type.

### Serialization

| Mode | Builder Call |
|:-----|:-------------|
| Default (Gson reflection) | None — works for records of primitives, strings, enums, nested records |
| Custom Gson | `.buildGson(g -> g.registerTypeAdapter(Foo.class, new FooAdapter()))` |
| Non-JSON | `.withCodec(customCodec)` — prefer subclassing `JsonResourceCodec` to retain REST API and schema generation compatibility |

### Validation

```java
ResourceTypeMeta.newBuilder(MyConfig.class)
    .resourceType(RESOURCE_TYPE)
    .buildValidator((config, errors) -> {
        errors.requireNotNull(config.endpoint(), "endpoint");
        errors.requireInRange(config.maxRetries(), 0, 10, "maxRetries");
    })
    .buildActionSet(b -> b
        .withValidatingCreate(MyManager::validateCreate)
        .withValidatingModify(MyManager::validateModify))
    .build();
```

| Type | Fires |
|:-----|:------|
| Static (`buildValidator`) | At load time, before persistence |
| Runtime (`withValidatingCreate` / `withValidatingModify`) | Depends on running system state |

### Action Sets

| Default Actions | Read, ListResources, Create, Modify, Delete, Move, Copy, Rename |
|:----------------|:-------------------------------|
| Opt out | `.buildActionSet(b -> b.create(null).copy(null))` |
| Empty (read-only system resources) | `.withActionSet(ResourceActionSet.EMPTY)` |

### REST API Exposure

```java
.buildRouteDelegate(b -> b
    .openApiGroupName("my-module")
    .openApiTagName("Database Connections")
    .addSearchField("name")
    .configSchema(DatabaseConnection.class)
    .supportsExtraDataFiles(false))
```

| Annotation | Effect |
|:-----------|:-------|
| `@Required` | Field required in REST creation payloads |
| `@Description` | OpenAPI description |
| `@FormCategory` | UI form grouping |
| `@Label` | UI form label |
| `@FormField(FormFieldType.X)` | UI form field type override |
| `@Minimum`, `@Maximum` | Numeric range validation |
| `@DefaultValue` | UI form default |

`configSchema(T.class)` generates JSON Schema via reflection plus OpenAPI annotations.

### Cross-Resource References

```java
.buildReferenceDelegate(b -> b
    .referenceProperty("auditProfile", ref -> ref
        .targetType(AuditProfile.RESOURCE_TYPE)
        .value(MyConfig::auditProfileName)
        .onUpdate(MyConfig::withAuditProfileName)
        .caseSensitive(true)))
```

| Constraint | Detail |
|:-----------|:-------|
| Rename propagation | Platform calls `onUpdate` automatically during rename — eliminates stale-reference bugs |
| Record immutability | `onUpdate` must return a new resource instance. Provide `with*` helper methods on the record |

### Audit, Status, Overview Delegates

| Delegate | Purpose |
|:---------|:--------|
| `ResourceAuditDelegate` | Controls audit log formatting. Default logs human-readable JSON diffs. `ResourceAuditDelegate.DISABLED` for sensitive resources |
| `ResourceStatusDelegate` | Exposes metrics and health checks via `instanceMetric`, `instanceHealthCheck`, `categoryMetric` |
| `ResourceEntityDelegate` | Controls Platform Overview page presence. Default includes; `ResourceEntityDelegate.NONE` opts out |

---
[Back to Overview](./OVERVIEW.md)
