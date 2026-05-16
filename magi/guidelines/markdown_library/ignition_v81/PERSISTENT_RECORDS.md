# PersistentRecords

Configuration storage system used in 8.1 (superseded by resource collections in 8.3).

### Defining a PersistentRecord

```java
public class MyRecord extends PersistentRecord {
    public static final RecordMeta<MyRecord> META =
        new RecordMeta<>(MyRecord.class, "MyRecord");

    public static final IdentityField     ID       = new IdentityField(META);
    public static final StringField       NAME     = new StringField(META, "name", SFieldFlags.SMANDATORY);
    public static final IntField          PORT     = new IntField(META, "port").setDefault(8080);
    public static final BooleanField      ENABLED  = new BooleanField(META, "enabled").setDefault(true);
    public static final EncodedStringField SECRET  = new EncodedStringField(META, "secret");
    public static final ReferenceField<ParentRecord> PARENT =
        new ReferenceField<>(META, ParentRecord.META, "parent_id");
    public static final BlobField         PAYLOAD  = new BlobField(META, "payload");

    static {
        META.addField(NAME).addField(PORT).addField(ENABLED)
            .addField(SECRET).addField(PARENT).addField(PAYLOAD);
    }

    @Override
    public RecordMeta<?> getMeta() { return META; }
}
```

| Field Type | Use |
|:-----------|:----|
| `IdentityField` | Auto-incrementing primary key. Every record needs one — defined by `RecordMeta.idField()` |
| `StringField`, `IntField`, `BooleanField`, `LongField` | Primitive values |
| `EncodedStringField` | Reversibly-encoded secrets. **Replaced by `SecretConfig` in 8.3.** Migration uses `DefaultRecordEncodingDelegate` |
| `ReferenceField<T>` | Foreign-key relationship; pair with the referenced record's `META.idField()` |
| `BlobField` | Binary payload |

### Registering and Using PersistentRecords

```java
// In GatewayHook.setup(context):
context.getSchemaUpdater().updatePersistentRecords(MyRecord.META);

// Query:
try (PersistenceSession session = context.getPersistenceInterface().getSession()) {
    SQuery<MyRecord> query = new SQuery<>(MyRecord.META).eq(MyRecord.NAME, "x");
    MyRecord record = session.queryOne(query);

    record.setPort(9090);
    record.setEnabled(true);
    session.execute();              // single sessions auto-commit on close
}
```

- **Listener:** `RecordListenerAdapter` / `RecordInstanceForeman` — listen for create/update/delete on a record type. Wire in `startup`, unwire in `shutdown`.
- **Redundancy:** PersistentRecord changes replicate to redundant backup automatically. No manual sync code required.

---
[Back to Overview](./OVERVIEW.md)
