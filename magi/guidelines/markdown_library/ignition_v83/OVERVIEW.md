# Ignition v8.3 SDK Module Development Library

These guidelines define strict rules for module development against the Ignition 8.3 SDK. They supersede 8.1 patterns. Use alongside the cross-version rules at `~/.claude/enforcement/guidelines/guideline_documents/markdown/ignition_guidelines.md`, which apply to every Ignition module regardless of platform version.

## Critical Mandates (Read First)
- **No Hot-Restart** — `setup`/`startup`/`shutdown` run exactly once per Gateway lifetime; install/upgrade/uninstall queue until restart.
- **`modules.json` Acceptance** — production modules require positive-acceptance entries; deployment automation must manage it.
- **Java 17 LTS** — records, sealed classes, pattern matching, switch expressions, text blocks; preview features prohibited.
- **Jakarta Servlets** — `jakarta.servlet.*` exclusively; never `javax.servlet.*`.
- **Protobuf-Based Gateway Network** — Java serialization is prohibited for 8.3↔8.3; implement `ProtobufSerializable`.
- **Resource Collections Replace PersistentRecord** — `ResourceTypeMeta` for new modules.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Module Lifecycle Changes](./MODULE_LIFECYCLE_CHANGES.md)
3. [Resource Collections](./RESOURCE_COLLECTIONS.md)
4. [ResourceTypeMeta](./RESOURCE_TYPE_META.md)
5. [Secrets API](./SECRETS_API.md)
6. [@RpcInterface and Protobuf RPC](./RPC.md)
7. [Push Notifications](./PUSH_NOTIFICATIONS.md)
8. [Modern Extension Points](./EXTENSION_POINTS.md)
9. [OPC UA Drivers — Device + DeviceExtensionPoint](./OPC_UA_DRIVERS.md)
10. [Project System (ResourceCollection)](./PROJECT_SYSTEM.md)
11. [Designer Changes](./DESIGNER_CHANGES.md)
12. [Scripting Changes](./SCRIPTING_CHANGES.md)
13. [Redundancy and SnapshotStateProvider](./REDUNDANCY.md)
14. [Removed APIs](./REMOVED_APIS.md)
15. [Perspective Changes](./PERSPECTIVE_CHANGES.md)
16. [Launchers](./LAUNCHERS.md)
17. [Modern Naming Conventions](./NAMING_CONVENTIONS.md)
18. [Migration Sequence (8.1 → 8.3)](./MIGRATION_SEQUENCE.md)
19. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
20. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
21. [Style Summary](./STYLE_SUMMARY.md)
