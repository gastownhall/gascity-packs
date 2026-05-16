# Gateway Services

### Database Access via DatasourceManager

```java
try (SRConnection con = context.getDatasourceManager().getConnection("dbname")) {
    Dataset rows = con.runPrepQuery("SELECT id, name FROM widgets WHERE active = ?", true);
    con.runPrepUpdate("UPDATE widgets SET name = ? WHERE id = ?", newName, id);
}
```

| Operation | API |
|:----------|:----|
| Convenience query | `runQuery`, `runPrepQuery`, `runScalarQuery`, `runPrepUpdate` |
| Transactions | `setAutoCommit(false)`, `commit()`, `rollback()` on `SRConnection`. **Transactions do not span `SRConnection` instances.** |
| Schema | `DBTableSchema.addRequiredColumn(name, DataType, EnumSet<ColumnProperty>)`; `verifyAndUpdate(con)` creates/adds — **never drops or alters** |
| Parameterization | All user-supplied values flow through `?` placeholders, never string concatenation |

**Always use try-with-resources for `SRConnection`.** A leaked connection pins a database pool slot for the JVM lifetime.

### ExecutionManager

```java
context.getExecutionManager().register("MyModule", "PollDevices", () -> {
    // periodic work
}, 5, TimeUnit.SECONDS);

// Variable interval — implement SelfSchedulingRunnable
context.getExecutionManager().register("MyModule", "Adaptive", new SelfSchedulingRunnable() {
    @Override public void run() { /* ... */ }
    @Override public long getNextExecDelayMillis() { return adaptiveDelay; }
});

// One-shot
context.getExecutionManager().executeOnce(() -> { /* ... */ });

// Private engine for CPU-bound or long-running work
BasicExecutionEngine engine = new BasicExecutionEngine("MyModule-Workers", 4);
// ... use engine ...
engine.shutdown();   // in module shutdown()

// Cleanup
context.getExecutionManager().unRegister("MyModule", "PollDevices");
```

Tasks are keyed by `(owner, name)`; re-register replaces. Always `unRegister` every registered task in `shutdown()`.

### AlarmManager

```java
AlarmFilter filter = new AlarmFilterBuilder()
    .isState(AlarmState.ActiveUnacked)
    .priority_gt(AlarmPriority.Medium)
    .build();
AlarmQueryResult result = context.getAlarmManager().queryStatus(filter);

// Module-defined alarm
BasicAlarmConfiguration config = new BasicAlarmConfiguration();
BasicAlarmDefinition def = new BasicAlarmDefinition("HighTemp");
config.add(def);
AlarmEvaluator eval = context.getAlarmManager().registerAlarm(qualifiedPath, config);
eval.update(value);

// Cleanup
eval.release();   // in module shutdown
```

### AuditManager

```java
DefaultAuditRecord record = new DefaultAuditRecord(
    AuditAction.CONFIG_UPDATE,
    actorPrincipal,
    targetPath,
    StatusCode.GOOD,
    Instant.now());
context.getAuditManager().getProfile(projectName).audit(record);
```

---
[Back to Overview](./OVERVIEW.md)
