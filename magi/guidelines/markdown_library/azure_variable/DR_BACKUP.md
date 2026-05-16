# Disaster Recovery and Backup

### App Configuration Geo-Replication

Standard tier supports geo-replication:
- Configure replica in paired region
- Automatic failover on regional outage
- Near-zero RPO for configuration data
- Applications automatically redirect to healthy replica

**Enable geo-replication for production stores.** The cost is negligible compared to outage impact.

### Key Vault Redundancy

Built-in:
- Zone-redundant replication within region
- Soft delete (default enabled, 7-90 day retention)
- Purge protection prevents permanent deletion during retention

For cross-region disaster recovery:
- Maintain secondary vault in paired region
- Sync secrets via automated process or manual procedure
- Document failover procedure for applications

### Backup Procedures

**App Configuration**:
```bash
az appconfig kv export --name {config} --destination file --path backup.json
```

**Key Vault** (per-secret; no native vault-level backup):
```bash
az keyvault secret backup --vault-name {vault} --name {secret} --file {secret}.backup
```

Automate backups via scheduled pipeline. Store backups in separate subscription/tenant for catastrophic recovery scenarios.

### Recovery Procedures

```text
Step 1: Create new vault/store from infrastructure as code
Step 2: Restore configuration from backup or source control
Step 3: Restore secrets from backup files
Step 4: Update application configuration to point to recovered resources
Step 5: Validate application functionality
```

**Test recovery annually at minimum.** Untested recovery procedures fail when needed.

---
[Back to Overview](./OVERVIEW.md)
