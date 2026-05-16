# Designer/Client → Gateway RPC

Designer/Client to Gateway RPC in 8.1 is **Java-serialization based**.

### ModuleRPCFactory Pattern

```java
// Common scope: define interface
public interface MyRpc {
    List<DeviceStatus> listDevices();
    QualityCode writeSetpoint(String deviceId, double value);
}

// Gateway scope: implement
public class MyRpcImpl implements MyRpc {
    private final GatewayContext context;
    public MyRpcImpl(GatewayContext context) { this.context = context; }
    @Override public List<DeviceStatus> listDevices() { ... }
    @Override public QualityCode writeSetpoint(String deviceId, double value) { ... }
}

// GatewayHook
@Override
public Object getRPCHandler(ClientReqSession session, String projectName) {
    return new MyRpcImpl(context);
}

// Designer/Client
MyRpc rpc = ModuleRPCFactory.create("com.company.module", MyRpc.class);
```

| Constraint | Detail |
|:-----------|:-------|
| Interface scope | Common (`GCD`) so Designer/Client/Gateway all see the type |
| Argument and return types | All must implement `Serializable` with stable `serialVersionUID` |
| EDT discipline | **Never call RPC from the EDT synchronously.** Wrap in `SwingWorker` or background thread to avoid freezing the Designer |
| Heavy types | Avoid sending Swing components, JDBC objects, or other non-portable types over RPC |

---
[Back to Overview](./OVERVIEW.md)
