# Scripting Modules

Registering scripting functions exposed to Python (Jython 2.7) in the `system.*` namespace.

### Registering Script Modules

Override `initializeScriptManager` in any scope's hook:

```java
@Override
public void initializeScriptManager(ScriptManager manager) {
    super.initializeScriptManager(manager);
    manager.addScriptModule(
        "system.modulename",
        new MyScriptFunctions(context),
        new PropertiesFileDocProvider());
}
```

Methods exposed to Python must be public, non-synthetic, no `$` in name, and not throw `PyIgnoreMethodTag`.

### Annotations

| Annotation | Purpose |
|:-----------|:--------|
| `@ScriptFunction(docBundlePrefix="ClassName")` | Links to documentation properties file |
| `@ScriptArg("name")` | Overrides Java parameter name when `-parameters` is not set |
| `@KeywordArgs(names=..., types=...)` on `(PyObject[], String[])` signature | Use `PyArgumentMap.interpretPyArgs` to extract typed args |
| `@NoHint` | Hides method from autocomplete but keeps it callable |

### Documentation Properties File

```properties
# MyScriptFunctions.properties (colocated with the class)
readDevice.desc=Read the current value from the named device.
readDevice.param.deviceName=The configured device name.
readDevice.returns=The latest QualifiedValue for the device.
```

---
[Back to Overview](./OVERVIEW.md)
