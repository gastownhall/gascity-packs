# External Tables and Data Lake Integration

### External Table Fundamentals

External tables query data in cloud storage **without loading**:

```sql
CREATE EXTERNAL TABLE ext_events (
    event_id NUMBER AS (value:event_id::NUMBER),
    event_timestamp TIMESTAMP_NTZ AS (value:timestamp::TIMESTAMP_NTZ),
    event_type VARCHAR AS (value:type::VARCHAR),
    payload VARIANT AS (value:payload)
)
WITH LOCATION = @s3_stage/events/
FILE_FORMAT = (TYPE = 'PARQUET')
PARTITION BY (event_date)
AUTO_REFRESH = TRUE;
```

### Partition Columns

Define partition columns matching file path structure:

```text
s3://bucket/events/event_date=2025-01-15/file.parquet
```

```sql
ALTER EXTERNAL TABLE ext_events ADD PARTITION (event_date = '2025-01-15') 
    LOCATION 's3://bucket/events/event_date=2025-01-15/';

-- Or refresh to detect new partitions
ALTER EXTERNAL TABLE ext_events REFRESH;
```

### Auto-Refresh

```sql
CREATE EXTERNAL TABLE ext_events ...
AUTO_REFRESH = TRUE;
```

Requires cloud event notification configuration (same as Snowpipe). Metadata refresh consumes cloud services credits.

### External Table Performance

External tables are **inherently slower than native tables**:

- No micro-partition statistics.
- No clustering optimization.
- Network overhead for every query.
- Limited query pushdown to file format.

| Use external tables for | Load to native tables when |
|:------------------------|:---------------------------|
| Query-in-place before deciding to load | Frequently queried |
| Rarely-queried historical data | Performance-sensitive |
| Compliance-required external storage | Joins benefit from clustering |
| Federated queries | — |

### Iceberg Tables

Snowflake supports Apache Iceberg for open table format interoperability:

```sql
CREATE ICEBERG TABLE iceberg_events (
    event_id BIGINT,
    event_timestamp TIMESTAMP_NTZ,
    event_type STRING
)
CATALOG = 'SNOWFLAKE'
EXTERNAL_VOLUME = 'iceberg_volume'
BASE_LOCATION = 'events/';
```

Iceberg tables enable: query from non-Snowflake engines (Spark, Presto, Trino), open file formats with table semantics, schema evolution without rewriting data, time travel via Iceberg snapshots.

---
[Back to Overview](./OVERVIEW.md)
