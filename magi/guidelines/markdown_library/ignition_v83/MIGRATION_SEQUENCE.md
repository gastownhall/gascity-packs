# Migration Sequence (8.1 → 8.3)

| Step | Action |
|:----:|:-------|
| 1 | JDK upgrade to 17. Address illegal reflective access, removed APIs, module system warnings |
| 2 | Bump SDK coordinates to 8.3.0 in build scripts. Recompile and triage compilation failures by category |
| 3 | Project-wide `javax.servlet.*` → `jakarta.servlet.*` rename |
| 4 | OPC UA driver rewrite against `Device` + `DeviceExtensionPoint` (largest single migration cost for driver modules) |
| 5 | Convert `PersistentRecord` configuration to resource records with `ResourceTypeMeta`. `DefaultRecordEncodingDelegate` handles `EncodedStringField` → `SecretConfig.Inline` transparently |
| 6 | Optionally migrate `ModuleRPCFactory` RPC to `@RpcInterface`. Legacy continues to work |
| 7 | Implement `ProtobufSerializable` and register with `MetroProtobufRegistry` for any custom Gateway Network message types |
| 8 | Update `Resource.getData()` callers from `@Nullable byte[]` to `Optional<ImmutableBytes>` |
| 9 | Remove all reliance on hot-restart behavior. Audit `setup`/`startup` for unbounded operations |
| 10 | Update production deployment workflows for `data/modules.json` acceptance |
| 11 | Full regression test on 8.3 — redundancy failover, Gateway restart, signing verification |
| 12 | Set `requiredIgnitionVersion` to `8.3.0`; rebuild and sign |

---
[Back to Overview](./OVERVIEW.md)
