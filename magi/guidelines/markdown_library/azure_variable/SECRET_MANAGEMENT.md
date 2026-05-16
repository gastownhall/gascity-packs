# Secret Management Patterns

### Rotation Schedule

| Secret Type | Frequency | Method |
|:------------|:----------|:-------|
| Database passwords | 90 days | Automated via Azure Function or Logic App |
| API keys | 90-180 days | Provider-dependent; some support automated rotation |
| Service principal secrets | 180 days | Azure AD automated rotation |
| Certificates | 30 days before expiry | Key Vault auto-renewal or manual process |
| Encryption keys | Annual or per compliance | Key version rotation; gradual data re-encryption |

### Rotation Process

```text
Step 1: Generate new secret value
Step 2: Store new version in Key Vault
Step 3: Update consuming service credential (database user, API portal)
Step 4: Verify new credential functionality
Step 5: Maintain previous version for grace period (in-flight requests)
Step 6: Disable previous version after validation
```

### Connection String Patterns

**Forbidden** — credentials embedded in connection strings stored outside Key Vault:
```
Server=myserver.database.windows.net;Database=mydb;User Id=admin;Password=P@ssw0rd!
```

**Required Pattern A** — full connection string as a Key Vault secret, App Config referenced:
```
OrderService:Database:ConnectionString → Key Vault reference
```

**Required Pattern B** — decomposed; password separately, runtime composition:
```
OrderService:Database:Server     = myserver.database.windows.net   (App Configuration)
OrderService:Database:Database   = mydb                            (App Configuration)
OrderService:Database:UserId     = admin                           (App Configuration)
OrderService:Database:Password   → Key Vault reference
```

The single-secret approach is simpler; the decomposed approach enables sharing non-sensitive components.

---
[Back to Overview](./OVERVIEW.md)
