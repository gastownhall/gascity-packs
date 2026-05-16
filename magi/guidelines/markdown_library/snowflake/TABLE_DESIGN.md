# Table Design and Data Types

### Type Selection Principles

Choose the most specific type that accurately represents the domain:

| Data Category | Recommended Type | Avoid |
|:--------------|:-----------------|:------|
| Integers | `NUMBER(p,0)` with appropriate precision | `FLOAT` for integers; oversized precision |
| Decimals | `NUMBER(p,s)` with explicit scale | `FLOAT` for financial data |
| Monetary | `NUMBER(19,4)` or `NUMBER(19,2)` | `FLOAT`, `DOUBLE` |
| Text (bounded) | `VARCHAR(n)` with reasonable limit | `VARCHAR(16777216)` for everything |
| Text (unbounded) | `VARCHAR` without length | Arbitrary large limits |
| Booleans | `BOOLEAN` | `VARCHAR`, `NUMBER`, strings like `'Y'`/`'N'` |
| Dates | `DATE` | `VARCHAR`, `TIMESTAMP` for date-only |
| Timestamps | `TIMESTAMP_NTZ` (default), `TIMESTAMP_LTZ`, `TIMESTAMP_TZ` | `VARCHAR`, inconsistent types |
| Semi-structured | `VARIANT` | Stringly-typed JSON in `VARCHAR` |
| Binary | `BINARY` | Base64 in `VARCHAR` |

### Timestamp Strategy

Snowflake offers three timestamp types:

| Type | Use case |
|:-----|:---------|
| `TIMESTAMP_NTZ` | No timezone; stores wall clock time; business events where source timezone is irrelevant or unknown |
| `TIMESTAMP_LTZ` | Stores UTC internally, displays in session timezone; user-facing applications with timezone awareness |
| `TIMESTAMP_TZ` | Stores value with timezone offset; preserving original timezone context |

**Standardize on one type per table.** Mixing timestamp types invites comparison bugs and implicit conversions. `TIMESTAMP_NTZ` with UTC values is the safest default for analytical workloads.

### NOT NULL and Defaults

Apply `NOT NULL` constraints where business logic prohibits nulls. Snowflake enforces these constraints on insert/update.

```sql
CREATE TABLE order_line_item (
    order_line_item_id NUMBER(19,0) NOT NULL,
    order_id NUMBER(19,0) NOT NULL,
    product_id NUMBER(19,0) NOT NULL,
    quantity NUMBER(10,0) NOT NULL DEFAULT 1,
    unit_price NUMBER(19,4) NOT NULL,
    created_at TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);
```

### Primary Keys, Foreign Keys, and Unique Constraints

Snowflake supports constraint declarations but **does not enforce them by default**. Constraints serve as:

- Documentation of intended relationships.
- Hints to the query optimizer for join elimination.
- Metadata for BI tools that read constraint information.

Enable enforcement only if you accept the performance overhead:

```sql
ALTER TABLE order_line_item ADD CONSTRAINT pk_order_line_item PRIMARY KEY (order_line_item_id) RELY;
ALTER TABLE order_line_item ADD CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES order(order_id) RELY;
```

`RELY` tells the optimizer to trust the constraint without enforcement. Use `ENFORCED` only when runtime validation is worth the insert/update cost.

### Transient and Temporary Tables

| Type | Time Travel | Fail-Safe | Persistence | Use case |
|:-----|:-----------:|:---------:|:-----------:|:---------|
| Permanent | 0–90 days | 7 days | Permanent | Production data |
| Transient | 0–1 day | None | Permanent | Staging, intermediate |
| Temporary | 0–1 day | None | Session | Query scratch space |

```sql
CREATE TRANSIENT TABLE staging.load_buffer (
    ...
) DATA_RETENTION_TIME_IN_DAYS = 0;

CREATE TEMPORARY TABLE session_metrics AS
SELECT ...;
```

Transient and temporary tables reduce storage costs by eliminating Fail-safe overhead. **Don't use them for data that cannot be regenerated.**

---
[Back to Overview](./OVERVIEW.md)
