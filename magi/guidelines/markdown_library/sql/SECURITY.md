# Security Practices

### Principle of Least Privilege

- Application accounts receive only the permissions required for their function.
- Separate accounts for read-only reporting, read-write transactional, and administrative operations.
- Never use `sa`, `root`, or superuser accounts for application connections.
- Revoke `PUBLIC` privileges on sensitive schemas and objects.
- Application user: SELECT, INSERT, UPDATE, DELETE only on required tables.
- Read-only user for reporting: SELECT only.
- **Never grant TRUNCATE, DROP, CREATE to application users.**
- Use row-level security for multi-tenant applications.

### Role-Based Access Control

```sql
-- PostgreSQL role hierarchy
CREATE ROLE app_readonly;
GRANT USAGE ON SCHEMA public TO app_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;

CREATE ROLE app_readwrite;
GRANT app_readonly TO app_readwrite;
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_readwrite;

CREATE USER order_service WITH PASSWORD '***';
GRANT app_readwrite TO order_service;

-- Create application user with specific permissions
CREATE USER app_user WITH PASSWORD 'strong_password';
GRANT CONNECT ON DATABASE myapp TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- Create read-only reporting user
CREATE USER report_user WITH PASSWORD 'strong_password';
GRANT CONNECT ON DATABASE myapp TO report_user;
GRANT USAGE ON SCHEMA public TO report_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO report_user;
```

### SQL Injection Prevention

- Use parameterized queries for all dynamic input; **no exceptions**.
- Never concatenate user input into SQL strings.
- Stored procedures do not inherently prevent injection if they use dynamic SQL internally.
- ORM-generated queries are generally safe; raw SQL escapes ORM protections and requires scrutiny.
- Whitelist validation for dynamic table/column names.

```sql
-- PostgreSQL prepared statement
PREPARE user_by_email (text) AS
    SELECT id, email, first_name
    FROM user
    WHERE email = $1;
EXECUTE user_by_email('user@example.com');
```

```python
-- Application layer (Python)
cursor.execute(
    "SELECT * FROM user WHERE email = %s AND status = %s",
    (email, status)
)
```

```python
-- NEVER do string concatenation
query = "SELECT * FROM user WHERE email = '" + email + "'"
```

### Sensitive Data Handling

- Encrypt sensitive columns at rest using database-native encryption or application-layer encryption.
- Mask or redact sensitive data in non-production environments.
- Audit access to sensitive tables through database audit logging.
- Implement row-level security for multi-tenant data isolation where supported.

### Row-Level Security

```sql
-- PostgreSQL RLS
ALTER TABLE customer_data ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON customer_data
    USING (tenant_id = current_setting('app.current_tenant')::INTEGER);

-- PostgreSQL RLS for app role
ALTER TABLE order ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON order
    FOR ALL
    TO app_user
    USING (tenant_id = current_setting('app.tenant_id')::int);

-- SQL Server RLS
CREATE FUNCTION dbo.fn_tenant_predicate(@tenant_id INT)
RETURNS TABLE
WITH SCHEMABINDING
AS
    RETURN SELECT 1 AS result WHERE @tenant_id = SESSION_CONTEXT(N'tenant_id');

CREATE SECURITY POLICY tenant_policy
    ADD FILTER PREDICATE dbo.fn_tenant_predicate(tenant_id) ON dbo.customer_data;
```

### Data Masking

For non-production environments:

- Use dynamic data masking for development/testing access.
- Consider static masking for persistent test databases.
- Mask: names, emails, addresses, phone numbers, SSNs, financial data.

```sql
-- SQL Server Dynamic Data Masking
ALTER TABLE app_user ALTER COLUMN email_address ADD MASKED WITH (FUNCTION = 'email()');
ALTER TABLE app_user ALTER COLUMN phone_number ADD MASKED WITH (FUNCTION = 'partial(0,"XXX-XXX-",4)');
```

### Encryption at Rest

- Enable Transparent Data Encryption (TDE) for production databases.
- Use Always Encrypted for highly sensitive columns (credit cards, SSNs).
- Manage encryption keys in dedicated key management systems (Azure Key Vault, AWS KMS, HashiCorp Vault).
- Document key rotation procedures.

### Connection Security

- Require TLS for all database connections; reject unencrypted connections.
- Use certificate authentication or managed identity where possible; minimize password-based authentication.
- Rotate credentials regularly; store in secret management systems, not configuration files.
- Limit connection sources through firewall rules and database-level access controls.

### Audit Logging

```sql
-- Audit table structure
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    user_id BIGINT,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    old_values JSONB,
    new_values JSONB,
    query_text TEXT,
    application_name VARCHAR(100),
    client_addr INET
);

-- Generic audit trigger
CREATE OR REPLACE FUNCTION audit_trigger()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (
        table_name,
        operation,
        user_id,
        old_values,
        new_values,
        query_text,
        application_name,
        client_addr
    ) VALUES (
        TG_TABLE_NAME,
        TG_OP,
        current_setting('app.user_id', true)::BIGINT,
        CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN to_jsonb(OLD) END,
        CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN to_jsonb(NEW) END,
        current_query(),
        current_setting('application_name'),
        inet_client_addr()
    );
    RETURN CASE
        WHEN TG_OP = 'DELETE' THEN OLD
        ELSE NEW
    END;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Apply to sensitive tables
CREATE TRIGGER tr_audit_user
AFTER INSERT OR UPDATE OR DELETE ON user
FOR EACH ROW EXECUTE FUNCTION audit_trigger();
```

- Enable native audit logging for DDL changes, failed login attempts, and access to sensitive tables.
- Integrate database audit logs with centralized security monitoring.
- Retain audit logs according to compliance requirements; automate archival.

### Secret and Credential Hygiene

- Do not embed credentials in stored procedures, functions, triggers, or views.
- Do not store third-party API keys in database tables unless encrypted and strictly access-controlled; prefer external secret stores.

---
[Back to Overview](./OVERVIEW.md)
