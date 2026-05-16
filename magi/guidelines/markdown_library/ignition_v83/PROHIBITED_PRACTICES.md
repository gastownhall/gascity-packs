# Prohibited Practices

### Never Do

- Use `javax.servlet.*` imports — all servlet code must use `jakarta.servlet.*`.
- Use Java serialization for objects crossing 8.3-to-8.3 Gateway Network — implement `ProtobufSerializable` and register with `MetroProtobufRegistry`.
- Assume modules hot-restart at runtime — plan deployment around Gateway restarts.
- Cache plaintext secrets — hold the `Secret<?>` instance; fetch `Plaintext` on demand within try-with-resources; let `close()` zero the buffer.
- Reference `com.inductiveautomation.xopc.driver.api.*` — the package is **removed**. Use `Device` + `DeviceExtensionPoint`.
- Reference `EventBus` — use `EventManager`.
- Reference `RuntimeStateProvider` — use `SnapshotStateProvider`.
- Block `setup()` or `startup()` on network/database/external API. Dispatch via `ExecutionManager.executeOnce` or a private engine.
- Store large binary data (images, files, media) in resource attributes — use `ProjectResourceBuilder.putData` for binary payloads.
- Mutate a `ProjectResource` — they are **immutable**. Use `ProjectResourceBuilder` to produce new instances.
- Register different `ProtoRpcSerializer` instances on Gateway and proxy sides — symmetry is required.
- Bypass `data/modules.json` acceptance for production deployments — operator acceptance is a security boundary.

---
[Back to Overview](./OVERVIEW.md)
