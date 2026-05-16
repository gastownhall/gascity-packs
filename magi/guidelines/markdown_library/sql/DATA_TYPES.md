# Data Types and Constraints

### Type Selection Principles

- Choose the smallest type that accommodates the domain with headroom for growth.
- **Never use strings for non-string data**: dates, numbers, booleans, enums stored as `VARCHAR` are prohibited.
- Be explicit about precision and scale for decimals; `DECIMAL(19, 4)` for currency, not `FLOAT` or `DOUBLE`.
- Consistency across related columns: all amount columns use the same precision/scale.

### String Types

- `VARCHAR(n)` with an appropriate limit for variable-length strings; don't default to `VARCHAR(255)` blindly.
- `TEXT` or `VARCHAR(MAX)` for unbounded content (descriptions, notes, JSON blobs).
- `CHAR(n)` only for fixed-width codes: `CHAR(3)` for currency codes, `CHAR(2)` for country codes.
- Specify collation explicitly when case sensitivity or locale-specific sorting matters.
- `NVARCHAR` (SQL Server) or UTF-8 collation for Unicode data; ASCII-only assumptions break internationally.

| Field | Length |
|:------|:------:|
| Email addresses | `VARCHAR(254)` (RFC 5321 max) |
| URLs | `VARCHAR(2048)` (practical browser limit) |
| Phone numbers | `VARCHAR(20)` (international format with extensions; ITU-T E.164 max) |
| Names | `VARCHAR(100)` minimum; some names are long |
| Codes/identifiers | Match the specification exactly |

### Numeric Types

| Type | Use |
|:-----|:----|
| `INTEGER` (32-bit) | Counts, quantities, identifiers within 2 billion range |
| `BIGINT` (64-bit) | Identifiers in high-volume systems, epoch timestamps, large counters |
| `SMALLINT` | Constrained ranges (status codes, small enumerations) |
| `TINYINT` (SQL Server) | Very small ranges (0–255) |
| `DECIMAL(p, s)` | Exact numeric values: money, rates, measurements requiring precision |
| `FLOAT` / `DOUBLE` | Scientific data where approximate representation is acceptable |
| `NUMERIC` | Synonymous with `DECIMAL` in most databases |

**Currency and money:**

- Never use `FLOAT` or `REAL` for money; precision loss accumulates.
- Never use `MONEY` type in SQL Server; it has only 4 decimal places and implicit conversion issues.
- Use `DECIMAL(19, 4)` as a standard money type; adjust precision for currencies with more decimals.
- Store amounts in the smallest unit (cents, paise) as integers when precision is paramount.

```sql
price DECIMAL(19,4) NOT NULL
quantity INTEGER NOT NULL DEFAULT 0
latitude DOUBLE PRECISION
id BIGINT GENERATED ALWAYS AS IDENTITY
```

### Temporal Types

- `TIMESTAMP WITH TIME ZONE` for points in time; store in UTC, convert at display layer.
- `TIMESTAMP` (without timezone) only when the value is timezone-agnostic (scheduled local time).
- `DATE` for calendar dates without time component.
- `TIME` for time-of-day without date; rare in practice.
- `INTERVAL` for durations when the database supports it; otherwise store as seconds/minutes in integer.

```sql
created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
birth_date DATE NOT NULL
business_hours_start TIME NOT NULL
```

**SQL Server specific:**

- Use `DATETIME2(3)` or `DATETIME2(7)` instead of `DATETIME`; more precision, larger range, better storage.
- Use `DATETIMEOFFSET` when timezone information must be preserved.
- Avoid `SMALLDATETIME`; the minute-level precision rarely suffices.

**PostgreSQL specific:**

- `TIMESTAMPTZ` is the alias for `TIMESTAMP WITH TIME ZONE`.
- All `timestamptz` values are stored in UTC internally; display conversion happens at session level.
- Use `generate_series()` with intervals for time-based test data.

### Boolean Type

- Use native `BOOLEAN` type where supported (PostgreSQL, MySQL 8+).
- For databases without native boolean, use `SMALLINT` with check constraint `CHECK (column IN (0, 1))`.
- Never use `CHAR(1)` with `'Y'`/`'N'` or `'T'`/`'F'`; it's stringly typed and error-prone.
- SQL Server: Use `BIT` type; it stores efficiently and converts properly.

### Binary Data

- `BYTEA` (PostgreSQL) or `VARBINARY` (SQL Server) for binary data.
- Store large binaries (files, images) in blob storage with database storing the reference.
- Hash values (SHA-256, MD5) belong in fixed-length binary columns, not hex strings.
- Always specify expected length for hash columns: `BINARY(32)` for SHA-256.

### JSON and Semi-Structured Data

- Use native JSON types (`JSONB` in PostgreSQL, `JSON` in MySQL) when schema flexibility is genuinely required.
- Index JSON paths that participate in queries; unindexed JSON queries scan entire columns.
- Avoid JSON for structured data that fits relational modeling; JSON in RDBMS is an escape hatch, not a design pattern.
- Validate JSON schema at application layer or with database check constraints where supported.
- PostgreSQL `JSONB` is preferred over `JSON` for query performance (binary storage, indexable).
- Use JSON path expressions for extraction: `data->>'field'` (PostgreSQL), `JSON_VALUE(data, '$.field')` (SQL Server).

```sql
metadata JSONB NOT NULL DEFAULT '{}'::jsonb
audit_payload JSON NOT NULL

-- Index for JSONB queries
CREATE INDEX ix_user_metadata_tags ON user USING GIN ((metadata->'tags'));
```

### XML Data

- Use sparingly; JSON has largely replaced XML for semi-structured data.
- Native XML types allow XPath queries and schema validation.
- Index XML columns only if queried frequently; XML indexes are expensive.
- Consider storing XML as VARCHAR if only storing/retrieving without querying.

### Geographic and Spatial Data

For location-aware applications:

- PostGIS extension (PostgreSQL) or `GEOGRAPHY`/`GEOMETRY` types (SQL Server).
- Store coordinates as geographic points, not separate lat/long columns.
- Use spatial indexes for proximity queries.
- Be explicit about coordinate reference systems (SRID 4326 for WGS84/GPS coordinates).

### Constraints

Every column should have the maximum constraint set that reflects business rules:

- `NOT NULL` is the default assumption; nullable columns require justification.
- `CHECK` constraints for domain validation: positive amounts, valid status values, date ranges.
- `UNIQUE` constraints for natural keys and business identifiers that must not duplicate.
- `DEFAULT` values for columns with sensible defaults; explicit defaults are better than application-layer magic.

```sql
-- Check constraint for positive amounts
CONSTRAINT ck_order_amount_positive CHECK (amount > 0)

-- Check constraint for valid status
CONSTRAINT ck_order_status_valid CHECK (status IN ('pending', 'processing', 'completed', 'cancelled'))

-- Check constraint for date range
CONSTRAINT ck_subscription_dates_valid CHECK (end_date > start_date)

-- Check constraint for email format (basic)
CONSTRAINT ck_user_email_format CHECK (email_address LIKE '%@%.%')
```

### Enumerated Values

- Prefer check constraints over enum types for maintainability: `CHECK (status IN ('pending', 'active', 'cancelled'))`.
- Alternatively, use lookup tables with foreign keys for values that need metadata or translations.
- Native `ENUM` types (MySQL, PostgreSQL) are acceptable but complicate migrations when values change.
- Lookup tables provide: descriptions, sort order, active/inactive flags, localization support.
- Document the enum values in schema comments regardless of implementation choice.

### Nullable Columns: When to Allow

Nullability requires justification. Valid reasons:

- The value genuinely may not exist (spouse name for unmarried person).
- The value is unknown at insert time and will be populated later (`verified_at` before verification).
- Optional relationships (`manager_id` for top-level employees).
- Third-party data where values are sometimes missing.

Invalid reasons to allow `NULL`:

- "We don't know the requirement yet" — define it.
- "Empty string is the same as null" — no, pick one.
- "It's easier" — no, it creates three-valued logic complications.

---
[Back to Overview](./OVERVIEW.md)
