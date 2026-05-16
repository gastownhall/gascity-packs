# @RpcInterface and Protobuf RPC

The annotation-driven Protobuf RPC pattern for 8.3.

### The Pattern

```java
// Common scope (GCD)
@RpcInterface(packageId = "com.company.module")
public interface DeviceRpc {
    DeviceStatus getStatus(String deviceId);
    QualityCode writeSetpoint(String deviceId, double value);
}

// Gateway scope — standard Java class, no special base
public class DeviceRpcImpl implements DeviceRpc {
    private final GatewayContext context;
    public DeviceRpcImpl(GatewayContext context) { this.context = context; }
    @Override public DeviceStatus getStatus(String deviceId)             { ... }
    @Override public QualityCode writeSetpoint(String deviceId, double value) { ... }
}

// GatewayHook
@Override
public Optional<GatewayRpcImplementation> getRpcImplementation() {
    return Optional.of(GatewayRpcImplementation.of(
        ProtoRpcSerializer.DEFAULT_INSTANCE,
        new DeviceRpcImpl(context)));
}

// Designer/Client (proxy)
DeviceRpc rpc = GatewayConnection.getRpcInterface(
    ProtoRpcSerializer.DEFAULT_INSTANCE,
    "com.company.module",
    DeviceRpc.class);
```

| Aspect | Detail |
|:-------|:-------|
| `packageId` | Namespaces interfaces across modules |
| Implementation base | Standard Java class — no special base required |

### ProtoRpcSerializer

```java
ProtoRpcSerializer serializer = ProtoRpcSerializer.newBuilder()
    .registerGsonType(MyValueType.class)
    .registerProtobufType(MyProtoType.class, MyProtoType.PARSER)
    .build();
```

| Behavior | Detail |
|:---------|:-------|
| Default | `ProtoRpcSerializer.DEFAULT_INSTANCE` handles primitives, common Ignition types (`QualifiedValue`, `TagPath`, `Dataset`), records of primitives |
| Symmetric requirement | The **same serializer instance** MUST be registered on both Gateway and proxy sides. Mismatches fail at runtime with opaque errors |

### Async Invocation

```java
new Task<DeviceStatus>(() -> rpc.getStatus(deviceId))
    .onSuccess(status -> updateUi(status))
    .onFailure(err    -> showError(err))
    .run();
```

| API | Use |
|:----|:----|
| `com.inductiveautomation.ignition.client.util.gui.progress.Task` | Wraps potentially-throwing functions; `onSuccess` / `onFailure` callbacks; avoids blocking the EDT |
| `SwingWorker` | Remains valid for Designer-side wrapping of synchronous RPC calls |

### Legacy ModuleRPCFactory (Deprecated)

Retained for 8.1 backward compatibility. Uses Java serialization. Migrate to `@RpcInterface` opportunistically.

### RPC Error Handling

- Catch `RpcException` for network/protocol failures.
- Catch general `Exception` for implementation-thrown exceptions.
- **Never catch `Throwable`** — let `Error`s propagate.

---
[Back to Overview](./OVERVIEW.md)
