# Semi-Structured Data Handling

### VARIANT Type

Store JSON, Avro, ORC, Parquet data in VARIANT columns:

```sql
CREATE TABLE events (
    event_id NUMBER,
    event_data VARIANT
);

INSERT INTO events 
SELECT $1, PARSE_JSON($2) FROM VALUES (1, '{"type": "click", "page": "/home"}');
```

### Querying VARIANT Data

```sql
SELECT 
    event_data:type::VARCHAR as event_type,
    event_data:page::VARCHAR as page,
    event_data:metadata.source::VARCHAR as source,
    event_data:items[0].product_id::NUMBER as first_product
FROM events;
```

Type casting (`::TYPE`) is required for non-VARIANT output.

### FLATTEN for Array Processing

```sql
SELECT 
    e.event_id,
    f.value:product_id::NUMBER as product_id,
    f.value:quantity::NUMBER as quantity
FROM events e,
    LATERAL FLATTEN(input => e.event_data:items) f;
```

| Option | Behavior |
|:-------|:---------|
| `OUTER => TRUE` | Preserve rows with NULL/empty arrays |
| `MODE => 'ARRAY'` / `'OBJECT'` / `'BOTH'` | Control what gets flattened |
| `RECURSIVE => TRUE` | Flatten nested structures recursively |

### Semi-Structured Best Practices

**Declare typed columns for frequently queried paths:**

```sql
CREATE TABLE events (
    event_id NUMBER,
    event_type VARCHAR,
    event_timestamp TIMESTAMP_NTZ,
    event_data VARIANT
);
```

**Computed columns for derived values:**

```sql
ALTER TABLE events ADD COLUMN 
    user_region VARCHAR AS (event_data:user.region::VARCHAR);
```

**Index frequently queried VARIANT paths with Search Optimization** (Enterprise):

```sql
ALTER TABLE events ADD SEARCH OPTIMIZATION ON EQUALITY(event_data:user.id);
```

### JSON Validation

Validate JSON structure on load:

```sql
SELECT TRY_PARSE_JSON(column_value) FROM staged_data;  -- Returns NULL for invalid JSON
```

Use `TRY_*` functions for graceful handling of malformed data.

---
[Back to Overview](./OVERVIEW.md)
