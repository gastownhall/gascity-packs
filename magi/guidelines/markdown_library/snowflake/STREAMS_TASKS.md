# Streams and Tasks

### Stream Fundamentals

Streams track changes (CDC) on tables:

```sql
CREATE STREAM stream_customer_changes ON TABLE customers;

SELECT * FROM stream_customer_changes;  -- Returns INSERTs, UPDATEs, DELETEs since last consumed
```

**Stream metadata columns:**

| Column | Meaning |
|:-------|:--------|
| `METADATA$ACTION` | `INSERT` or `DELETE` |
| `METADATA$ISUPDATE` | `TRUE` if part of UPDATE |
| `METADATA$ROW_ID` | Unique row identifier |

Updates appear as DELETE + INSERT pairs with `METADATA$ISUPDATE = TRUE`.

### Stream Types

| Type | Tracks | Use case |
|:-----|:-------|:---------|
| Standard (default) | All changes from current offset | General CDC |
| Append-only | Inserts only | More efficient for insert-only tables |

```sql
CREATE STREAM stream_events ON TABLE events APPEND_ONLY = TRUE;
```

### Stream Consumption

Streams advance automatically when used in DML transactions:

```sql
INSERT INTO customer_history
SELECT 
    customer_id,
    CURRENT_TIMESTAMP() as change_timestamp,
    METADATA$ACTION as action,
    *
FROM stream_customer_changes
WHERE METADATA$ACTION = 'INSERT' OR METADATA$ISUPDATE = TRUE;
-- Stream offset advances after successful INSERT
```

### Task Fundamentals

Tasks schedule SQL execution:

```sql
CREATE TASK task_process_changes
    WAREHOUSE = etl_wh
    SCHEDULE = '5 MINUTE'
    WHEN SYSTEM$STREAM_HAS_DATA('stream_customer_changes')
AS
    INSERT INTO customer_history
    SELECT * FROM stream_customer_changes;
```

### Task Configuration

| Schedule | Syntax |
|:---------|:-------|
| Cron | `SCHEDULE = 'USING CRON 0 * * * * America/Los_Angeles'` |
| Interval | `SCHEDULE = '5 MINUTE'` |

**Conditional execution:** `WHEN` clause prevents empty runs.

**Serverless tasks** (no warehouse required):

```sql
CREATE TASK task_lightweight
    USER_TASK_MANAGED_INITIAL_WAREHOUSE_SIZE = 'XSMALL'
    SCHEDULE = '1 MINUTE'
    WHEN SYSTEM$STREAM_HAS_DATA('stream_customer_changes')
AS
    CALL process_incremental();
```

### Task DAGs

Chain tasks for complex pipelines:

```sql
CREATE TASK task_step_1 WAREHOUSE = etl_wh SCHEDULE = '1 HOUR' AS ...;
CREATE TASK task_step_2 WAREHOUSE = etl_wh AFTER task_step_1 AS ...;
CREATE TASK task_step_3 WAREHOUSE = etl_wh AFTER task_step_2 AS ...;

-- Enable the DAG (root task only)
ALTER TASK task_step_1 RESUME;
```

### Stream + Task Patterns

**Incremental aggregation:**

```sql
MERGE INTO daily_summary t
USING (SELECT ... FROM stream_transactions WHERE ...) s
ON t.date = s.date AND t.product_id = s.product_id
WHEN MATCHED THEN UPDATE SET ...
WHEN NOT MATCHED THEN INSERT ...;
```

### Task Monitoring

```sql
SELECT * FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
    TASK_NAME => 'task_process_changes',
    SCHEDULED_TIME_RANGE_START => DATEADD(HOUR, -24, CURRENT_TIMESTAMP())
));
```

**Alert on task failures — failed tasks don't automatically retry.**

---
[Back to Overview](./OVERVIEW.md)
