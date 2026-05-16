# Module Lifecycle Changes

| Aspect | 8.1 | 8.3 |
|:-------|:----|:----|
| Method signatures | `setup(GatewayContext)`, `startup(LicenseState)`, `shutdown()` | **Unchanged** |
| Invocation count per Gateway lifetime | Many (hot-restart) | **Exactly once** |
| Bounded execution time | Recommended | **Required** — other modules wait |
| Module activation gate | None | `data/modules.json` acceptance |

`setup()` and `startup()` MUST complete in bounded time. Dispatch any blocking work to `ExecutionManager.executeOnce` or a private engine.

---
[Back to Overview](./OVERVIEW.md)
