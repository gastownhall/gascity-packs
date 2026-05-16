# Naming Conventions

### General Rules

- **Tables**: Singular nouns in `snake_case`: `user`, `order_item`, `payment_transaction`
- **Columns**: Descriptive `snake_case` without table name prefix: `created_at`, `email_address`, `total_amount`
- **Primary Keys**: `id` for surrogate keys; `{table}_id` when referencing as foreign key in another table
- **Foreign Keys**: `{referenced_table}_id`: `user_id`, `order_id`, `parent_category_id`
- **Indexes**: `ix_{table}_{columns}`: `ix_user_email`, `ix_order_item_order_id_product_id`
- **Unique Constraints**: `uq_{table}_{columns}`: `uq_user_email`, `uq_product_sku`
- **Check Constraints**: `ck_{table}_{description}`: `ck_order_total_positive`, `ck_user_age_valid`
- **Foreign Key Constraints**: `fk_{table}_{referenced_table}` or `fk_{table}_{column}_{referenced_table}`: `fk_order_item_order`, `fk_order_user_id_user`
- **Default Constraints**: `df_{table}_{column}`: `df_user_created_at`, `df_order_status`
- **Triggers**: `tr_{table}_{event}_{description}`: `tr_order_after_insert_audit`, `tr_user_before_update_validate`
- **Sequences**: `seq_{table}_{column}` or `seq_{purpose}`: `seq_order_id`, `seq_invoice_number`
- **Schemas**: Lowercase, descriptive: `core`, `audit`, `staging`, `archive`, `reporting`
- **Synonyms**: `syn_{original_object}`: `syn_legacy_user`

```sql
-- CORRECT
CONSTRAINT pk_user PRIMARY KEY (id)
CONSTRAINT fk_order_user_id_user FOREIGN KEY (user_id) REFERENCES user(id)
CONSTRAINT uq_user_email UNIQUE (email)
CONSTRAINT ck_order_total_positive CHECK (total_amount > 0)
CREATE INDEX ix_order_user_id_created_at ON order(user_id, created_at);
```

### Boolean Columns

Prefix boolean columns with `is_`, `has_`, `can_`, or `should_` to indicate their nature:

- `is_active`, `is_deleted`, `is_verified`
- `has_subscription`, `has_two_factor`
- `can_login`, `can_export`
- `should_notify`, `should_retry`

### Temporal Columns

| Suffix | Use |
|:------:|:----|
| `_at` | Timestamps: `created_at`, `updated_at`, `deleted_at`, `verified_at` |
| `_on` | Dates without time: `birth_on`, `hired_on`, `expires_on` |
| `_until` / `_from` | Ranges: `valid_from`, `valid_until` |
| `_duration` | Intervals: `session_duration`, `lock_duration` |

### Computed and Derived Columns

- Prefix computed columns with `calc_` or use descriptive names that indicate derivation: `calc_total_with_tax`, `full_name`.
- Document the computation logic in column comments or schema documentation.
- Prefer persisted computed columns when the expression is deterministic and read-heavy.

### Avoid These Patterns

- Reserved words as identifiers: `user`, `order`, `group`, `select` require quoting and cause confusion; prefer `app_user`, `purchase_order`, `user_group`.
- Abbreviations that sacrifice clarity: `usr`, `ord`, `txn`, `amt`, `FName`, `TotalAmount` are prohibited; write `user`, `order`, `transaction`, `amount`, `first_name`, `total_amount`.
- Hungarian notation or type prefixes: `tbl_user`, `int_count`, `str_name` are prohibited.
- Pluralized table names: `users`, `orders`, `products` create inconsistency with join aliases and ORM mappings.
- Underscores at the start: `_internal_column` is ambiguous; use schemas for internal/staging objects.
- CamelCase or PascalCase: `OrderItem`, `userId` violates convention; use `order_item`, `user_id`.
- Numbers without context: `column1`, `table2` are meaningless.
- Overly long names that exceed 64 characters (many databases have identifier length limits).

---
[Back to Overview](./OVERVIEW.md)
