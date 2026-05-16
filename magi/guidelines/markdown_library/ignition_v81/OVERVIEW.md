# Ignition v8.1 SDK Module Development Library

These guidelines define strict rules for module development against the Ignition 8.1 SDK. Use alongside the cross-version rules at `~/.claude/enforcement/guidelines/guideline_documents/markdown/ignition_guidelines.md`, which apply to every Ignition module regardless of platform version.

## Critical Mandates (Read First)
- **Hot-Restart Discipline** — `setup`/`startup`/`shutdown` may run multiple times per Gateway lifetime; release every resource.
- **Abstract Hooks Only** — extend `AbstractGatewayModuleHook`, `AbstractDesignerModuleHook`, `AbstractClientModuleHook`; never implement the raw interfaces.
- **Three Scopes** — `G` (Gateway), `D` (Designer), `C` (Client); concatenate for multi-scope jars; `CD` for Vision; `GCD` only for cross-scope contracts.
- **Servlet API** — `javax.servlet.*` in 8.1; Jakarta migration is an 8.3 concern.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Module Hook Lifecycle](./MODULE_HOOK_LIFECYCLE.md)
3. [module.xml Manifest](./MODULE_XML_MANIFEST.md)
4. [PersistentRecords](./PERSISTENT_RECORDS.md)
5. [Extension Points](./EXTENSION_POINTS.md)
6. [Designer/Client → Gateway RPC](./RPC.md)
7. [Push Notifications](./PUSH_NOTIFICATIONS.md)
8. [Scripting Modules](./SCRIPTING_MODULES.md)
9. [Tag System](./TAG_SYSTEM.md)
10. [OPC UA Drivers (8.1)](./OPC_UA_DRIVERS.md)
11. [Vision Components](./VISION_COMPONENTS.md)
12. [Designer Workspaces](./DESIGNER_WORKSPACES.md)
13. [Store-and-Forward Datasinks](./DATASINKS.md)
14. [Gateway Services](./GATEWAY_SERVICES.md)
15. [Status Pages and Homepage Panels](./STATUS_PAGES.md)
16. [Localization](./LOCALIZATION.md)
17. [Module Services](./MODULE_SERVICES.md)
18. [Redundancy](./REDUNDANCY.md)
19. [Module Signing](./MODULE_SIGNING.md)
20. [Build Systems](./BUILD_SYSTEMS.md)
21. [Version Deltas Within 8.1.x](./VERSION_DELTAS.md)
22. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
23. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
24. [Style Summary](./STYLE_SUMMARY.md)
