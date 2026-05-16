# Stored Procedures and Functions

### When to Use Stored Procedures

- Complex, multi-step operations that benefit from reduced round-trips.
- Data-intensive transformations that should not traverse the network.
- Operations requiring elevated privileges executed by less-privileged application accounts.
- Encapsulating business logic that must remain consistent across multiple applications.

### When to Avoid Stored Procedures

- Simple CRUD operations better expressed in application code.
- Logic requiring unit testing with application test frameworks.
- Operations that need to evolve rapidly with application releases.
- When debugging and version control integration are priorities.

### Function Types

- **Scalar functions**: Return a single value; usable in `SELECT` lists and `WHERE` clauses.
- **Table-valued functions**: Return result sets; usable in `FROM` clause.
- **Aggregate functions**: Custom aggregations when built-ins don't suffice.
- Prefer set-based logic in functions; row-by-row cursor operations kill performance.

### Stored Procedure Standards

- Use explicit parameter names and data types matching application expectations.
- Return meaningful status codes or result sets; avoid output parameters when result sets suffice.
- Document input validation, expected preconditions, and side effects.
- Handle errors explicitly; use `TRY...CATCH` (SQL Server) or `EXCEPTION` blocks (PostgreSQL).

### Naming Conventions

- Prefix procedures with `sp_` only if organizational convention demands it; otherwise use descriptive names. **Never use `sp_` for user procedures in SQL Server (reserved for system).**
- Functions: `fn_calculate_discount`, `fn_format_address`.
- Procedures: `create_order`, `process_payment_batch`, `archive_old_records`.

### Versioning

- Stored procedures live in version control alongside application code.
- Deploy procedure changes through migration scripts, not ad-hoc execution.
- Test procedures in non-production environments before deployment.

### Procedure Contract and Determinism

- Treat every procedure/function as a stable API: changing parameters, result shape, or semantics is a breaking change and must be versioned.
- Define input domain constraints inside the database when feasible:
  - Use CHECK constraints for column domains.
  - Use guard clauses for procedure parameters (reject invalid values early).
  - Do not rely on default schema resolution; always schema-qualify objects (for example, `dbo.purchase_order` in SQL Server, `public.purchase_order` or an explicit schema in PostgreSQL).

### Error Handling and Transaction Safety

- Procedures that perform writes must explicitly control transactions (either always own a transaction boundary or explicitly require the caller to own it). Document the expectation.
- **SQL Server guidance**:
  - Use `SET XACT_ABORT ON` for procedures that write data so runtime errors reliably abort and rollback.
  - Use `TRY...CATCH` and always rollback if `XACT_STATE()` indicates an active transaction.
- **PostgreSQL guidance**:
  - Use `EXCEPTION` blocks to map errors to clear failure modes.
  - Prefer raising meaningful exceptions (SQLSTATE and message) rather than returning ambiguous magic values.

```sql
-- SQL Server error handling template
CREATE PROCEDURE process_order @order_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRY
        BEGIN TRANSACTION;

        -- Business logic here

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0
            ROLLBACK TRANSACTION;

        THROW;
    END CATCH
END;
```

```sql
-- PostgreSQL error handling template
CREATE OR REPLACE FUNCTION process_order(p_order_id INTEGER)
RETURNS VOID AS $$
BEGIN
    -- Business logic here

EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to process order %: %', p_order_id, SQLERRM;
END;
$$ LANGUAGE plpgsql;
```

### Full PostgreSQL Function Example

```sql
-- PostgreSQL function with comprehensive error handling
CREATE OR REPLACE FUNCTION process_order(
    p_user_id BIGINT,
    p_items JSONB,
    p_payment_method VARCHAR(50)
)
RETURNS TABLE(
    order_id BIGINT,
    status VARCHAR(20),
    message TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_order_id BIGINT;
    v_total_amount DECIMAL(19,4) := 0;
    v_item JSONB;
BEGIN
    -- Validate input
    IF p_user_id IS NULL THEN
        RETURN QUERY SELECT NULL::BIGINT, 'error'::VARCHAR, 'User ID required'::TEXT;
        RETURN;
    END IF;

    -- Start transaction
    BEGIN
        -- Create order
        INSERT INTO order (user_id, payment_method, status)
        VALUES (p_user_id, p_payment_method, 'pending')
        RETURNING id INTO v_order_id;

        -- Add items
        FOR v_item IN SELECT * FROM jsonb_array_elements(p_items)
        LOOP
            INSERT INTO order_item (
                order_id,
                product_id,
                quantity,
                price
            )
            VALUES (
                v_order_id,
                (v_item->>'product_id')::BIGINT,
                (v_item->>'quantity')::INT,
                (v_item->>'price')::DECIMAL(19,4)
            );
            v_total_amount := v_total_amount +
                (v_item->>'quantity')::INT * (v_item->>'price')::DECIMAL(19,4);
        END LOOP;

        -- Update order total
        UPDATE order
        SET total_amount = v_total_amount
        WHERE id = v_order_id;

        -- Return success
        RETURN QUERY SELECT v_order_id, 'success'::VARCHAR, 'Order created'::TEXT;
    EXCEPTION
        WHEN OTHERS THEN
            -- Log error
            INSERT INTO error_log (error_message, error_detail, occurred_at)
            VALUES (SQLERRM, SQLSTATE, NOW());
            -- Return error
            RETURN QUERY SELECT NULL::BIGINT, 'error'::VARCHAR, SQLERRM::TEXT;
    END;
END;
$$;
```

### Avoiding Injection and Unsafe Dynamic SQL

- Avoid dynamic SQL unless absolutely required.
- If dynamic SQL is required:
  - SQL Server: use `sp_executesql` with typed parameters; never concatenate user input.
  - PostgreSQL: use `format()` with `%I` for identifiers and `%L` for literals; validate allowed values before building SQL.
  - Restrict dynamic object names to a safe allowlist (table names, column names, sort keys).

```sql
-- SQL Server safe dynamic SQL
DECLARE @sql NVARCHAR(MAX);
DECLARE @params NVARCHAR(MAX) = N'@user_id INT';

SET @sql = N'SELECT * FROM app_user WHERE id = @user_id';
EXEC sp_executesql @sql, @params, @user_id = @input_user_id;

-- PostgreSQL safe dynamic SQL with whitelist validation
CREATE OR REPLACE FUNCTION get_table_data(table_name text, limit_rows int)
RETURNS TABLE(data jsonb) AS $$
BEGIN
    -- Whitelist validation
    IF table_name NOT IN ('user', 'order', 'product') THEN
        RAISE EXCEPTION 'Invalid table name';
    END IF;
    IF limit_rows < 1 OR limit_rows > 1000 THEN
        RAISE EXCEPTION 'Invalid limit';
    END IF;
    -- Safe dynamic SQL with format() and quote_ident()
    RETURN QUERY EXECUTE format(
        'SELECT to_jsonb(t.*) FROM %I t LIMIT %s',
        table_name,
        limit_rows
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### Parameter Sniffing and Plan Stability (SQL Server)

- Be aware of parameter sniffing for procedures that run with very different parameter distributions.
- Prefer fixing root causes first (better indexes, better predicates, updated statistics).
- If plan instability is confirmed:
  - Consider `OPTION (RECOMPILE)` selectively for highly skewed parameters (accepting CPU tradeoff).
  - Consider local variables or `OPTIMIZE FOR` only with documented justification and measurable improvement.
  - Avoid global query hints as a first response; they often create future regressions.

### Set-Based Design and Avoiding Row-By-Row Work

- Procedures should be set-based by default.
- Avoid cursors and loops for business operations:
  - Replace with single `INSERT ... SELECT`, `UPDATE ... FROM`, or `MERGE`-equivalent patterns (use caution with `MERGE` on SQL Server due to known edge cases; prefer explicit UPDATE + INSERT when correctness demands).
  - When batching is required, implement bounded batches with deterministic ordering, and commit between batches to control log growth and lock duration.

### Result Shapes and Client Compatibility

- Procedures used by applications should return consistent column lists and stable types across releases.
- Avoid returning multiple unrelated result sets from a single procedure unless the caller contract explicitly requires it.
- Prefer returning:
  - A single primary result set plus a final status row; or
  - A single result set with a status column for each row (for bulk operations).

### Security Model for Procedures

- Prefer executing procedures with minimal caller privileges:
  - SQL Server: consider `EXECUTE AS OWNER` only when necessary and documented.
  - PostgreSQL: consider `SECURITY DEFINER` with strict ownership, restricted `search_path`, and careful SQL to avoid privilege escalation.
  - Restrict direct table access where feasible; grant execute on procedures and keep base tables locked down.

### Observability for Procedures

- Any procedure that performs complex writes should optionally accept a request correlation identifier (for example, `request_id UUID`) to support tracing and auditing.
- Log or persist critical operations (especially destructive ones) to an append-only audit table with:
  - `request_id`, actor identity, timestamp, operation name, and a summary of affected scope.

---
[Back to Overview](./OVERVIEW.md)
