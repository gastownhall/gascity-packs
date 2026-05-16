# Data Loading Strategies

### COPY INTO: Batch Loading

```sql
COPY INTO target_table
FROM @stage_name/path/
FILE_FORMAT = (TYPE = 'PARQUET')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
ON_ERROR = 'CONTINUE';
```

| Option | Purpose |
|:-------|:--------|
| `MATCH_BY_COLUMN_NAME` | Map source columns to target by name, not position |
| `ON_ERROR` | `ABORT_STATEMENT`, `CONTINUE`, `SKIP_FILE`, `SKIP_FILE_n` |
| `PURGE` | Delete staged files after successful load |
| `FORCE` | Reload files even if previously loaded (use sparingly) |

### File Format Configuration

Define reusable file formats:

```sql
CREATE FILE FORMAT parquet_format
    TYPE = 'PARQUET'
    COMPRESSION = 'SNAPPY';

CREATE FILE FORMAT csv_format
    TYPE = 'CSV'
    FIELD_DELIMITER = ','
    RECORD_DELIMITER = '\n'
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('NULL', 'null', '')
    EMPTY_FIELD_AS_NULL = TRUE
    ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE;
```

**Prefer Parquet or ORC** for analytical workloads — columnar, compressed, schema-preserving. CSV requires more configuration and loses type information.

### Stage Configuration

| Stage type | Use case |
|:-----------|:---------|
| Internal stages | Snowflake-managed storage; ad-hoc loads and testing |
| External stages | Reference cloud storage directly |

```sql
CREATE STAGE s3_raw_stage
    URL = 's3://bucket-name/raw/'
    STORAGE_INTEGRATION = s3_integration
    FILE_FORMAT = parquet_format;

CREATE STORAGE INTEGRATION s3_integration
    TYPE = EXTERNAL_STAGE
    STORAGE_PROVIDER = 'S3'
    ENABLED = TRUE
    STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::account:role/snowflake-access'
    STORAGE_ALLOWED_LOCATIONS = ('s3://bucket-name/');
```

Storage integrations authenticate **without embedding credentials**.

### Snowpipe: Continuous Ingestion

Snowpipe automates loading as files arrive — pay per file loaded, no warehouse required.

```sql
CREATE PIPE raw_pipe
    AUTO_INGEST = TRUE
    AS
    COPY INTO raw.events
    FROM @s3_raw_stage/events/
    FILE_FORMAT = parquet_format;
```

Configure cloud event notifications (S3 SQS, Azure Event Grid, GCS Pub/Sub) to trigger Snowpipe on file arrival. Monitor via `SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY`.

### Loading Best Practices

- **File sizing:** target 100–250MB compressed files. Files too small create overhead; files too large reduce parallelism.
- **File organization:** partition staged files by logical groupings (date, source system) to enable selective loading: `s3://bucket/raw/events/year=2025/month=01/day=15/file001.parquet`.
- **Idempotent loads:** use `MERGE` for upsert semantics; track loaded files in metadata tables; rely on Snowflake's automatic load history (14-day deduplication window).
- **Error handling:** log failed records — `COPY INTO target_table FROM @stage VALIDATION_MODE = 'RETURN_ERRORS';`.

### MERGE for Upserts

```sql
MERGE INTO target t
USING staged_changes s
ON t.id = s.id
WHEN MATCHED AND s.operation = 'DELETE' THEN DELETE
WHEN MATCHED THEN UPDATE SET 
    t.column1 = s.column1,
    t.column2 = s.column2,
    t.updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (id, column1, column2, created_at)
    VALUES (s.id, s.column1, s.column2, CURRENT_TIMESTAMP());
```

### Bulk Insert Performance

For large initial loads:

- Use larger warehouse sizes (parallelism scales with size).
- Load multiple files concurrently.
- Disable automatic clustering during load, enable after.
- Consider loading into staging table first, then `INSERT INTO ... SELECT` with transformations.

---
[Back to Overview](./OVERVIEW.md)
