# Stored Procedures and User-Defined Functions

### Stored Procedures

Snowflake supports JavaScript, Python, Java, Scala, and Snowflake Scripting (SQL) for procedures.

**Snowflake Scripting** (recommended for SQL-centric logic):

```sql
CREATE OR REPLACE PROCEDURE process_batch(batch_date DATE)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    DELETE FROM staging.daily_load WHERE load_date = :batch_date;
    
    INSERT INTO staging.daily_load
    SELECT * FROM source.events WHERE event_date = :batch_date;
    
    LET row_count := SQLROWCOUNT;
    
    RETURN 'Processed ' || :row_count || ' rows';
END;
$$;
```

**Python** (for complex logic, ML integration):

```sql
CREATE OR REPLACE PROCEDURE analyze_sentiment(text_column VARCHAR)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('snowflake-snowpark-python', 'textblob')
HANDLER = 'run'
AS
$$
def run(session, text_column):
    from textblob import TextBlob
    # Implementation
    return result
$$;
```

### User-Defined Functions (UDFs)

**Scalar UDFs** — return single value per row:

```sql
CREATE OR REPLACE FUNCTION mask_email(email VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
    REGEXP_REPLACE(email, '.+@', '***@')
$$;
```

**Table UDFs (UDTFs)** — return tables:

```sql
CREATE OR REPLACE FUNCTION explode_json(json_data VARIANT)
RETURNS TABLE (key VARCHAR, value VARIANT)
LANGUAGE SQL
AS
$$
    SELECT key, value FROM TABLE(FLATTEN(json_data))
$$;
```

### External Functions

Call external services (AWS Lambda, Azure Functions, GCP Cloud Functions):

```sql
CREATE EXTERNAL FUNCTION validate_address(address VARCHAR)
RETURNS VARIANT
API_INTEGRATION = address_api_integration
AS 'https://api.example.com/validate';
```

### Procedure vs Function Selection

| Characteristic | Stored Procedure | UDF |
|:---------------|:-----------------|:----|
| Return value | Single value, result set | Single value (scalar) or table |
| Side effects | Can modify data (INSERT, UPDATE, DELETE) | Read-only; no side effects |
| Transaction control | Can manage transactions | Executes within caller's transaction |
| Usage in queries | `CALL` statement only | Usable in `SELECT`, `WHERE`, etc. |

Use procedures for orchestration and data modification. Use functions for reusable transformations within queries.

### Performance Considerations

- SQL UDFs inline and optimize with the calling query.
- JavaScript/Python UDFs have initialization overhead; **avoid in row-by-row hot paths**.
- Vectorized Python UDFs (using Snowpark) batch rows for better performance.
- External functions add network latency; batch where possible.

---
[Back to Overview](./OVERVIEW.md)
