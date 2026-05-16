# Store-and-Forward Datasinks

Custom datasinks for module-specific historical data.

```java
public final class MyHistoryFlavor extends HistoryFlavor {
    public static final MyHistoryFlavor FLAVOR = new MyHistoryFlavor();
    private MyHistoryFlavor() { super("com.company.module.history.v1"); }
}

public class MyDatasink extends AbstractDatasourceSink {

    @Override
    public void initialize(SRConnection con) throws SQLException {
        DBTableSchema schema = new DBTableSchema("module_history")
            .addRequiredColumn("ts", DataType.Int8, EnumSet.of(ColumnProperty.NotNull))
            .addRequiredColumn("device", DataType.String, EnumSet.of(ColumnProperty.NotNull))
            .addRequiredColumn("payload", DataType.String, EnumSet.noneOf(ColumnProperty.class));
        schema.verifyAndUpdate(con);
    }

    @Override
    public void storeDataToDatasource(SRConnection con, HistoricalData data) throws SQLException {
        // write data to schema
    }

    @Override public boolean acceptsData(HistoryFlavor flavor)   { return MyHistoryFlavor.FLAVOR.equals(flavor); }
    @Override public boolean isLicensedFor(HistoryFlavor flavor) { return MyHistoryFlavor.FLAVOR.equals(flavor); }
}

// GatewayHook.startup
context.getHistoryManager().registerHistoryFlavor(MyHistoryFlavor.FLAVOR);
context.getHistoryManager().registerSink(new MyDatasink());

// GatewayHook.shutdown
context.getHistoryManager().unregisterSink(sink);
context.getHistoryManager().unregisterHistoryFlavor(MyHistoryFlavor.FLAVOR);

// From application code
context.getHistoryManager().storeHistory("MyDatasource", historicalData);
```

Store-and-forward handles buffering and retry automatically.

---
[Back to Overview](./OVERVIEW.md)
