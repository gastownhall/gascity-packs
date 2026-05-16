# Tag System

### Tag Read/Write

```java
TagProvider provider = context.getTagManager().getTagProvider("default");

CompletableFuture<List<QualifiedValue>> readFuture =
    provider.readAsync(paths, SecurityContext.emptyContext());

CompletableFuture<List<QualityCode>> writeFuture =
    provider.writeAsync(paths, values, securityContext);
```

Use `SecurityContext.emptyContext()` for Gateway-internal operations; use an explicit minimum-privilege context for user-initiated operations.

### SimpleTagProvider

Custom tag namespace owned by the module:

```java
SimpleTagProvider provider = new SimpleTagProvider("MyNamespace");
provider.startup(context);

provider.configureTagType(EXTENDED_TYPE, TagEditingFlags.STANDARD_STATUS, customColumns);
provider.configureTag("Devices/PLC1/Temperature", DataType.Float8, TagType.AtomicTag);

provider.registerWriteHandler("Devices/PLC1/Setpoint", (path, value) -> {
    // perform write
    return DataQuality.GOOD_DATA;
});

provider.updateValue("Devices/PLC1/Temperature", 72.5, DataQuality.GOOD_DATA);

// In module shutdown:
provider.shutdown();
```

---
[Back to Overview](./OVERVIEW.md)
