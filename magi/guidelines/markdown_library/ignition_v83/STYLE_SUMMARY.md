# Style Summary

| Element | Required Style |
|:--------|:---------------|
| **JVM** | Java 17 LTS; records, sealed classes, pattern matching, switch expressions, text blocks; preview features prohibited |
| **Servlet** | `jakarta.servlet.*` exclusively |
| **Lifecycle** | `setup`/`startup`/`shutdown` exactly once per Gateway lifetime; no hot-restart assumptions; bounded execution time |
| **Module activation** | `data/modules.json` acceptance required; deployment automation must edit it |
| **Configuration** | `ResourceTypeMeta`-based resource collections; records as data shape; lowercase-hyphenated `typeId`; register in `setup()` |
| **Resource handlers** | `SingletonResourceHandler` / `NamedResourceHandler` with `onChange` / `onResourceAdded`/`Updated`/`Removed`; `isRenameAware()` for identity preservation |
| **Validation** | `buildValidator` static + `withValidatingCreate`/`withValidatingModify` runtime |
| **REST API** | `buildRouteDelegate` with `configSchema`; OpenAPI annotations (`@Required`, `@FormField`, `@Minimum`, etc.) |
| **References** | `buildReferenceDelegate` with `targetType` + `value` + `onUpdate`; rename propagation automatic |
| **Audit/Status/Overview** | `ResourceAuditDelegate`, `ResourceStatusDelegate`, `ResourceEntityDelegate` for presence + formatting |
| **Secrets** | `SecretConfig` field on records; `Secret.create(ctx, cfg)`; `try (Plaintext pt = secret.getPlaintext())`; `SecretReferenceProperty` for renames |
| **RPC** | `@RpcInterface(packageId)` in common; standard Java impl in Gateway; symmetric `ProtoRpcSerializer.DEFAULT_INSTANCE` on both sides; `Task` / `SwingWorker` for async |
| **Push notifications** | `sendNotification(scope, moduleId, type, payload, serializer)`; receiver uses `FilteredPushNotification` with `dispatchOnEDT` |
| **Extension points** | Subclass platform `ExtensionPointType<Settings>`; record settings; `defaultSettings`/`validate`/`createX` overrides; `getWebUiComponent` for React UI |
| **OPC UA** | `Device` + `DeviceExtensionPoint`; async `CompletableFuture` I/O; `UaFolderNode`/`UaVariableNode.builder`; `AttributeFilters.getValue` for lazy resolution |
| **Project system** | `ResourceCollection` instead of `Project`; `ResourceCollectionManifest.title()`; `Resource.getData()` returns `Optional<ImmutableBytes>` |
| **Project injection** | `addImmutableProject(ProjectFileUtil.importFromZip(...))`; opaque, non-editable, excluded from backups/redundancy |
| **Designer save** | Async; `notifyProjectSaveStart`/`Done` off the EDT; throw to abort (no `SaveContext.abort()`) |
| **Scripting** | `@JythonElement` for static; `@ScriptFunction` for methods; `CompletionDescriptor` doc objects |
| **Redundancy** | `SnapshotStateProvider` with `takeSnapshot`/`restoreSnapshot`; not for config / history / transient caches |
| **Gateway Network** | Protobuf only for 8.3-to-8.3; `ProtobufSerializable` + `MetroProtobufRegistry.register()` |
| **Naming** | `lowercase-hyphenated` resource type IDs; `ResourceType.rootPath()` for paths; `QualifiedPath`/`QualifiedValue`/`QualifiedID` |
| **Defense in Depth** | Redundancy + resource discipline + signing/licensing + Protobuf RPC versioning + Secrets API + script error handling + Designer/Perspective/Vision parity + external monitoring |
| **Rule of Three** | Designer + Perspective + Vision (or Designer + Gateway + Client for headless) MUST agree before sign-off |

---
[Back to Overview](./OVERVIEW.md)
