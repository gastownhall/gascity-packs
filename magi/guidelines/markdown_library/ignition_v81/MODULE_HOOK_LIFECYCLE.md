# Module Hook Lifecycle

### Gateway Hook

`AbstractGatewayModuleHook` lifecycle:

| Phase | Required Work |
|:------|:--------------|
| `setup(GatewayContext context)` | Register extension points; update PersistentRecord schemas; register `ResourceTypeAdapter`s; declare module services. **Other managers are NOT yet started — do not query other modules.** Store the `GatewayContext` in a field for module lifetime use. |
| `startup(LicenseState licenseState)` | Register scripting modules; register history flavors and sinks; subscribe to module services; start scheduled tasks via `ExecutionManager`; register push-notification listeners; register status panels. |
| `shutdown()` | Unregister every counterpart of every `setup`/`startup` registration. Call `context.getHistoryManager().unregisterSink/unregisterHistoryFlavor`; `context.getExecutionManager().unRegister(owner, name)`; `BundleUtil.get().removeBundle(name)`; etc. |

- `setup()` may read the internal database in read-only mode but must not modify it. All modifications belong in `startup()`.
- The `GatewayContext` instance received in `setup()` is valid for the module's entire lifetime. Reuse the same instance everywhere; do not refetch.

### Designer Hook

`AbstractDesignerModuleHook` lifecycle:

| Phase | Required Work |
|:------|:--------------|
| `startup(DesignerContext context, LicenseState licenseState)` | `addBeanInfoSearchPath`; `registerResourceWorkspace`; `addAction` to `MenuBarMergeBundle`; register `ContextMenuProvider`s; register `UndoManager` actions; register `SearchProvider`s. |
| `shutdown()` | Remove `BundleUtil` bundles; dispose Swing timers/dialogs; unregister Designer-side resource workspaces. |

**EDT discipline:** Designer code runs on the Event Dispatch Thread. Never block `startup()` on network I/O, database queries, or RPC calls. Offload to `SwingWorker` or background threads.

### Client Hook

Client hooks are optional. Modules contributing only Vision components do not need a Client hook — the `CD`-scoped jar loads automatically when components are referenced by a window.

---
[Back to Overview](./OVERVIEW.md)
