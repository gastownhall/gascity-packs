# Core Principles

These guidelines define strict rules for module development against the Ignition 8.3 SDK. They supersede 8.1 patterns. Use alongside the cross-version rules at `~/.claude/enforcement/guidelines/guideline_documents/markdown/ignition_guidelines.md`, which apply to every Ignition module regardless of platform version.

**Scope:** All Ignition 8.3.x module development — resource-collection-based configuration, `ResourceTypeMeta`-driven REST/audit/status integration, dynamic Secrets API, Protobuf-based RPC via `@RpcInterface`, push notifications with explicit serializers, `Device` + `DeviceExtensionPoint` OPC UA drivers, Jakarta servlet integration, `SnapshotStateProvider` redundancy, project injection, `modules.json` acceptance.

**Runtime:**

| Component | Constraint |
|:----------|:-----------|
| JVM | Java 17 LTS required |
| Build | Gradle 8.5+ with `io.ia.sdk.modl` 0.4.x+ |
| Web Server | Jakarta EE 10 |
| Gateway Network | Protobuf-based |
| Signing | Gradle (PKCS#11 / HSM supported) or `module-signer.jar` |

**Authoritative source:** `~/.claude/enforcement/guidelines/guideline_documents/markdown/ignition_v83_module_doc.md`.

### No Hot-Restart

Modules in 8.3 only start and stop during Gateway startup and shutdown. Install, upgrade, and uninstall queue until the next Gateway restart. **Module code must NOT assume hot-restart is available.** Plan deployment around Gateway restarts.

### modules.json Acceptance

Modules in `user-lib/modules/` no longer auto-load without a positive-acceptance entry in `data/modules.json`. Production deployments require operators to accept new modules explicitly. Automation tooling must manage `modules.json` edits as part of deployment.

### Java 17 LTS

Java 17 LTS is the build and runtime target. Use Java 17 language features:

- Records
- Sealed classes
- Pattern matching
- Switch expressions
- Text blocks

Preview features are prohibited.

### Jakarta Servlets

Servlet imports use `jakarta.servlet.*` — **NEVER `javax.servlet.*`**. The Web Server upgraded from Java EE 8 to Jakarta EE 10.

### Protobuf-Based Gateway Network

Java serialization is **prohibited** for 8.3-to-8.3 Gateway Network communication. Custom message types must implement `com.inductiveautomation.metro.api.ProtobufSerializable` and register with `MetroProtobufRegistry.register()`. Java serialization is retained ONLY for 8.1↔8.3 backward-compatibility paths.

### Resource Collections Replace PersistentRecord

Configuration storage uses resource collections (`ResourceTypeMeta`) for new modules. `PersistentRecord` remains for backward compatibility and gradual migration only.

---
[Back to Overview](./OVERVIEW.md)
