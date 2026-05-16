# Core Principles

These guidelines define strict rules for module development against the Ignition 8.1 SDK. Use alongside the cross-version rules at `~/.claude/enforcement/guidelines/guideline_documents/markdown/ignition_guidelines.md`, which apply to every Ignition module regardless of platform version.

**Scope:** All Ignition 8.1 (8.1.0 through 8.1.x) module development — scripting modules, Vision components, OPC UA drivers, alarm/audit/auth/tag/history extension points, datasinks, push notifications, gateway status pages, designer workspaces, undo/redo, search-and-replace integration.

**Runtime:**

| Component | Constraint |
|:----------|:-----------|
| JVM | Java 11 for 8.1.0–8.1.32; Java 17 for 8.1.33+ |
| Build | Gradle 8.x with `io.ia.sdk.modl` plugin OR Maven with `ignition-maven-plugin` 1.0.x |
| Signing | `module-signer.jar` or Gradle `signModule` task |

**Authoritative source:** `~/.claude/enforcement/guidelines/guideline_documents/markdown/ignition_v81_module_doc.md`.

### Hot-Restart Discipline

Modules in 8.1 hot-restart while the Gateway runs. Install, upgrade, and uninstall trigger a module-only restart cycle. Module code must tolerate `setup` / `startup` / `shutdown` being invoked **multiple times** in a single Gateway lifetime. Every resource acquired must be released; every listener registered must be unregistered.

### Abstract Hooks Only

Every hook extends an Abstract base class:

- `AbstractGatewayModuleHook`
- `AbstractDesignerModuleHook`
- `AbstractClientModuleHook`

Direct interface implementation (`GatewayModuleHook`, etc.) breaks across SDK point releases.

### Three Scopes

| Scope | Letter | Purpose |
|:------|:------:|:--------|
| Gateway | `G` | Server-side execution (alarm pipeline, drivers, services) |
| Designer | `D` | Designer workspace UI, palette, BeanInfo |
| Client | `C` | Vision Client runtime |

Concatenate letters for multi-scope jars: `CD`, `GCD`. Vision component code lives in `CD`. Gateway-only services live in `G`. Common contracts shared across all three live in `GCD`. Designer-only UI lives in `D`.

### Resource Lifecycle Discipline

`shutdown()` must release every resource acquired in `setup()` or `startup()`. Orphaned listeners, schedulers, bundles, datasinks, and extension points pin the module's classloader and produce PermGen-style leaks across hot-restart cycles.

### Servlet API

Servlet imports use `javax.servlet.*` in 8.1. Jakarta migration is an 8.3 concern.

---
[Back to Overview](./OVERVIEW.md)
