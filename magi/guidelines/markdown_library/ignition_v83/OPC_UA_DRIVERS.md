# OPC UA Drivers — Device + DeviceExtensionPoint

OPC UA driver development uses the `Device` + `DeviceExtensionPoint` pattern. **`com.inductiveautomation.xopc.driver.api` is REMOVED.**

### Device Interface

```java
public final class MyDevice implements Device {

    @Override public CompletableFuture<Void> startup()  { ... }
    @Override public CompletableFuture<Void> shutdown() { ... }

    @Override public DeviceStatus getStatus() { return status; }

    @Override public CompletableFuture<ReadResult>   read(ReadContext ctx, List<ReadValueId> ids)        { ... }
    @Override public CompletableFuture<WriteResult>  write(WriteContext ctx, List<WriteValue> values)    { ... }
    @Override public CompletableFuture<BrowseResult> browse(BrowseContext ctx, BrowseDescription desc)   { ... }
}
```

| Constraint | Detail |
|:-----------|:-------|
| Async | Every I/O method returns `CompletableFuture`. **Synchronous I/O is prohibited** — drives connection management to async patterns throughout |
| `getStatus()` | Returns `DeviceStatus` (`DISCONNECTED`, `CONNECTING`, `CONNECTED`, `FAULTED`) |

### DeviceExtensionPoint

```java
public final class MyDeviceExtensionPoint extends DeviceExtensionPoint<MyDeviceSettings> {

    public MyDeviceExtensionPoint() {
        super(TYPE_ID, "MyModule.device.name", "MyModule.device.desc", MyDeviceSettings.class);
    }

    @Override
    public Optional<MyDeviceSettings> defaultSettings() {
        return Optional.of(MyDeviceSettings.DEFAULT);
    }

    @Override
    public Device createDevice(GatewayContext ctx,
                               DeviceContext deviceContext,
                               DecodedResource<ExtensionPointConfig<DeviceConfig, MyDeviceSettings>> resource,
                               MyDeviceSettings settings) {
        return new MyDevice(ctx, deviceContext, settings);
    }
}

// GatewayHook.getExtensionPoints() must include the DeviceExtensionPoint
```

### Address Space and Nodes

```java
UaFolderNode rootFolder = new UaFolderNode(
    deviceContext.getNodeContext(),
    deviceContext.nodeId(name),
    deviceContext.qualifiedName(name),
    new LocalizedText(name));

UaVariableNode variable = UaVariableNode.builder(deviceContext.getNodeContext())
    .setNodeId(deviceContext.nodeId(name + "/Temperature"))
    .setBrowseName(deviceContext.qualifiedName("Temperature"))
    .setDisplayName(new LocalizedText("Temperature"))
    .setDataType(BuiltinDataType.Float.getNodeId())
    .setTypeDefinition(Identifiers.BaseDataVariableType)
    .setAccessLevel(AccessLevel.READ_WRITE)
    .build();

variable.getFilterChain().addLast(
    AttributeFilters.getValue(ctx -> readLiveValue(name)));   // lazy resolution

deviceContext.getNodeManager().addNode(variable);
rootFolder.addOrganizes(variable);
```

### Subscription Model

| Mode | Detail |
|:-----|:-------|
| Default | Polls every subscribed tag at the subscription rate |
| Batched | Override `getSubscriptionModel()` returning a custom batching implementation for protocols where reads can be coalesced |

### Milo SDK 1.0 Migration

Some classes/packages from `milo-server-sdk` relocated or renamed. Update import statements accordingly when migrating from 8.1.

---
[Back to Overview](./OVERVIEW.md)
