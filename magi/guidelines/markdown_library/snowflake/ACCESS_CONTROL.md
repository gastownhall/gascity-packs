# Access Control and Security

### Role-Based Access Control (RBAC)

Snowflake implements hierarchical RBAC. Users are granted roles; roles are granted privileges on objects; roles can be granted to other roles.

### Standard Role Hierarchy

```text
ACCOUNTADMIN (use sparingly)
    └── SYSADMIN (owns all databases, warehouses)
        └── DATABASE_ADMIN (per-database admin)
            └── ETL_ROLE (data loading, transformation)
            └── ANALYST_ROLE (read access to curated data)
            └── BI_ROLE (read access for BI tools)
        └── WAREHOUSE_ADMIN (warehouse management)
    └── SECURITYADMIN (user and role management)
        └── USER_ADMIN (user creation, password resets)
    └── USERADMIN (user management only)
```

### Custom Role Patterns

```sql
-- ETL role for data engineering
CREATE ROLE etl_role;
GRANT USAGE ON DATABASE raw_db TO ROLE etl_role;
GRANT USAGE ON ALL SCHEMAS IN DATABASE raw_db TO ROLE etl_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA raw_db.bronze TO ROLE etl_role;
GRANT USAGE ON WAREHOUSE etl_wh TO ROLE etl_role;

-- Analyst role for data analysis
CREATE ROLE analyst_role;
GRANT USAGE ON DATABASE analytics_db TO ROLE analyst_role;
GRANT USAGE ON ALL SCHEMAS IN DATABASE analytics_db TO ROLE analyst_role;
GRANT SELECT ON ALL TABLES IN DATABASE analytics_db TO ROLE analyst_role;
GRANT SELECT ON ALL VIEWS IN DATABASE analytics_db TO ROLE analyst_role;
GRANT USAGE ON WAREHOUSE analytics_wh TO ROLE analyst_role;
```

### Future Grants

Automatically apply privileges to new objects:

```sql
GRANT SELECT ON FUTURE TABLES IN SCHEMA analytics_db.reporting TO ROLE analyst_role;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA analytics_db.reporting TO ROLE analyst_role;
```

**Without future grants, new objects require manual privilege grants** — an operational burden and security gap.

### Row Access Policies (Enterprise+)

```sql
CREATE ROW ACCESS POLICY region_filter AS (region_column VARCHAR) 
RETURNS BOOLEAN ->
    CURRENT_ROLE() IN ('ADMIN_ROLE') 
    OR region_column = CURRENT_USER_REGION();

ALTER TABLE sales ADD ROW ACCESS POLICY region_filter ON (sales_region);
```

Users see only rows matching their policy. Central policy management without view proliferation.

### Column-Level Security / Masking Policies (Enterprise+)

```sql
CREATE MASKING POLICY email_mask AS (val STRING) RETURNS STRING ->
    CASE 
        WHEN CURRENT_ROLE() IN ('ADMIN_ROLE', 'PII_ROLE') THEN val
        ELSE REGEXP_REPLACE(val, '.+@', '***@')
    END;

ALTER TABLE customers MODIFY COLUMN email SET MASKING POLICY email_mask;
```

### Object Tagging

```sql
CREATE TAG pii_classification ALLOWED_VALUES 'public', 'internal', 'confidential', 'restricted';
ALTER TABLE customers SET TAG pii_classification = 'confidential';
ALTER TABLE customers MODIFY COLUMN ssn SET TAG pii_classification = 'restricted';
```

Query tagged objects for audit and compliance reporting.

### Network Policies

```sql
CREATE NETWORK POLICY corporate_only
    ALLOWED_IP_LIST = ('203.0.113.0/24', '198.51.100.0/24')
    BLOCKED_IP_LIST = ('192.0.2.5');

ALTER ACCOUNT SET NETWORK_POLICY = corporate_only;
```

Apply policies at account or user level.

### Authentication Best Practices

- Enable **MFA** for all human users.
- Use key-pair authentication for service accounts.
- Integrate with identity providers (Okta, Azure AD) via SAML/SCIM.
- Rotate service account keys regularly.
- **Never embed credentials in application code.**

---
[Back to Overview](./OVERVIEW.md)
