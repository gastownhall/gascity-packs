# Secret Rotation Automation

### Automatic Rotation (Single Secret)

```bash
rotate_database_password() {
    local db_name="$1"
    local vault_path="secret/database/${db_name}"
    local new_password
    new_password=$(openssl rand -base64 32)
    local current_password
    current_password=$(vault kv get -field=password "${vault_path}")
    mysql -u admin -p"${current_password}" <<EOF
ALTER USER '${db_name}_user'@'%' IDENTIFIED BY '${new_password}';
FLUSH PRIVILEGES;
EOF
    vault kv put "${vault_path}" password="${new_password}" rotation_time="$(date -Iseconds)"
    signal_app_reload "${db_name}"
    sleep 5
    if ! mysql -u "${db_name}_user" -p"${new_password}" -e "SELECT 1" >/dev/null 2>&1; then
        echo "Failed to connect with new password, investigation required"
        return 1
    fi
}
```

### Dual-Secret Rotation (Zero-Downtime)

```text
Phase 1: Add new secret alongside existing
Phase 2: Update consumers to use new secret
Phase 3: Verify no consumer uses old secret (automated)
Phase 4: Remove old secret after grace period
```

---
[Back to Overview](./OVERVIEW.md)
