# Designer Changes

| Aspect | Behavior |
|:-------|:---------|
| Async save | Resource commit is now asynchronous. `notifyProjectSaveStart` and `notifyProjectSaveDone` on `DesignerModuleHook` are called **off the EDT** |
| `SaveContext.abort()` | **Removed.** Throw exceptions directly during the save process to abort |

---
[Back to Overview](./OVERVIEW.md)
