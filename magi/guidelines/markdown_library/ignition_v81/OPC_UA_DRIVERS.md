# OPC UA Drivers (8.1)

OPC UA driver development in 8.1 uses the `DriverType` / `DeviceType` pattern. **This pattern is REMOVED in 8.3**; see the v8.3 guidelines for migration to `DeviceExtensionPoint`.

### 8.1 Driver Architecture

| Component | Role |
|:----------|:-----|
| Settings record | `PersistentRecord` subclass holding device connection settings; foreign key to `DeviceSettingsRecord` parent |
| `DeviceType` subclass | `displayName`, `description`, settings record class, `getMeta()`, `createDevice(GatewayContext, DeviceContext, settingsRecord)` |
| `DriverType` subclass | Older 8.1 code only; newer 8.1 code uses `DeviceType` only |
| Device implementation | Implements `Driver` interface — `connect`, `disconnect`, `readBlocking`, `writeBlocking`, `browse`, etc. |
| Address space | Build OPC UA nodes via `UaFolderNode` / `UaVariableNode.builder`; install `AttributeFilters.getValue` for lazy resolution |

### Registration

Use the `DriverManager` service consumer pattern:

```java
public class MyGatewayHook extends AbstractGatewayModuleHook implements ModuleServiceConsumer {

    @Override
    public void setup(GatewayContext context) {
        this.context = context;
        context.getModuleServicesManager().subscribe(DriverManager.class, this);
    }

    @Override
    public void serviceReady(Class<?> serviceClass) {
        if (serviceClass == DriverManager.class) {
            DriverManager driverManager = context.getModuleServicesManager().getService(DriverManager.class);
            driverManager.registerDeviceType(new MyDeviceType());
        }
    }

    @Override
    public void serviceShutdown(Class<?> serviceClass) {
        // null out cached references
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
