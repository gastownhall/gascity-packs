# Resource Collections

The configuration storage system replacing the 8.1 `PersistentRecord` ORM.

### Singleton vs Named Resources

| Kind | Description | Examples |
|:-----|:------------|:---------|
| **Singleton** | Nameless, zero-or-one instance. Default declared in `ResourceTypeMeta` governs the absent state | Global system properties, default network configuration |
| **Named** | Individually identified instances within a flat namespace per resource type | Database connections, audit profiles, alarm notification profiles |

### Resource Class Pattern

```java
public record DatabaseConnection(
        String url,
        String username,
        SecretConfig password,
        int maxPoolSize,
        Duration connectTimeout) {

    public static final ResourceType RESOURCE_TYPE =
        new ResourceType("com.company.module", "database-connection");

    public static final DatabaseConnection DEFAULT = new DatabaseConnection(
        "jdbc:postgresql://localhost/db", "user", SecretConfig.EMPTY, 10, Duration.ofSeconds(5));

    public static final ResourceTypeMeta<DatabaseConnection> TYPE_META =
        ResourceTypeMeta.newBuilder(DatabaseConnection.class)
            .resourceType(RESOURCE_TYPE)
            .categoryNameKey("MyModule.databaseConnections")
            .defaultConfig(DEFAULT)
            .build();

    // Immutable record helpers for reference-property updates
    public DatabaseConnection withPassword(SecretConfig newPassword) {
        return new DatabaseConnection(url, username, newPassword, maxPoolSize, connectTimeout);
    }
}
```

| Element | Convention |
|:--------|:-----------|
| Data shape | Java record |
| `RESOURCE_TYPE` | `new ResourceType(moduleId, typeIdHyphenated)`; `typeId` is **lowercase-hyphenated** (`database-connection`) |
| `TYPE_META` | `ResourceTypeMeta.newBuilder(...).resourceType(...).categoryNameKey(...).singleton().defaultConfig(DEFAULT).build()` |
| `DEFAULT` | Used when resource absent and exposed via REST creation wizards |

### Registering Resource Types

Register in `GatewayHook.setup()` — **NOT `startup()`**. The configuration loader consumes the registry before `startup()` runs:

```java
@Override
public void setup(GatewayContext context) {
    this.context = context;
    context.getConfigurationManager()
           .getResourceTypeMetaRegistry()
           .register(DatabaseConnection.TYPE_META);
}
```

### SingletonResourceHandler / NamedResourceHandler

```java
SingletonResourceHandler<NetworkConfig> netHandler = SingletonResourceHandler
    .newBuilder(NetworkConfig.TYPE_META)
    .context(context)
    .onChange(this::applyNetworkConfig)
    .build();

NamedResourceHandler<DatabaseConnection> dbHandler = NamedResourceHandler
    .newBuilder(DatabaseConnection.TYPE_META)
    .context(context)
    .onResourceAdded((name, cfg)   -> openPool(name, cfg))
    .onResourceUpdated((name, cfg) -> reconfigurePool(name, cfg))
    .onResourceRemoved(name        -> closePool(name))
    .build();
```

| Constraint | Detail |
|:-----------|:-------|
| Callback timing | `onChange` fires on startup with current value AND on every modification |
| Absent resource | Singleton handler returns `DEFAULT` |
| Rename awareness | Subclass `NamedResourceHandler` and override `isRenameAware()` returning `true` to treat renames as identity-preserving modifications. Requires UUID attribute on resource metadata |
| Cleanup | `handler.shutdown()` in module `shutdown()` |

### Deployment Mode Inheritance

`dev`, `test`, and unnamed (production) modes layer collections. Active-mode collections override base collections. Module authors generally see a unified merged view; do not special-case modes unless implementing mode-specific validation or UI.

---
[Back to Overview](./OVERVIEW.md)
