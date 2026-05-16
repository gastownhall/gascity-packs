# Sentinel Integration and Monitoring

### Diagnostic Settings

Configure diagnostic settings on both services to stream logs to Log Analytics.

**App Configuration Diagnostics**:
- `HttpRequest` — All API requests with operation details
- `Audit` — Configuration changes with before/after values

**Key Vault Diagnostics**:
- `AuditEvent` — All operations including secret access, key usage, authentication attempts

Send to a Log Analytics workspace integrated with Sentinel. **Enable at vault/store creation; retrofit existing resources immediately.**

### Sentinel Analytics Rules

| Rule | Severity | Threshold | Detects |
|:-----|:---------|:----------|:--------|
| Unusual Secret Access | High | > 100 accesses / hour per identity | Excessive secret reads |
| After-Hours Configuration Changes | Medium | Outside business hours | Off-hours mutations |
| Failed Authentication | Critical | > 10 failures / 15 minutes | Brute force / credential stuffing |
| Secret Enumeration | Critical | > 3 list operations / 5 minutes | Reconnaissance |

### Reference KQL

**Unusual Secret Access**:
```kusto
AzureDiagnostics
| where ResourceType == "VAULTS"
| where OperationName == "SecretGet"
| summarize AccessCount = count() by CallerIPAddress, Identity, bin(TimeGenerated, 1h)
| where AccessCount > 100
```

**Configuration Changes Outside Business Hours**:
```kusto
AzureDiagnostics
| where ResourceType == "MICROSOFT.APPCONFIGURATION/CONFIGURATIONSTORES"
| where OperationName has "Write" or OperationName has "Delete"
| extend Hour = datetime_part("hour", TimeGenerated)
| where Hour < 8 or Hour > 18
```

**Failed Authentication Attempts**:
```kusto
AzureDiagnostics
| where ResourceType == "VAULTS"
| where ResultSignature == "Unauthorized" or ResultSignature == "Forbidden"
| summarize FailureCount = count() by CallerIPAddress, Identity, bin(TimeGenerated, 15m)
| where FailureCount > 10
```

**Secret Enumeration Detection**:
```kusto
AzureDiagnostics
| where ResourceType == "VAULTS"
| where OperationName == "SecretList"
| summarize ListCount = count() by CallerIPAddress, Identity, bin(TimeGenerated, 5m)
| where ListCount > 3
```

### Workbooks and Dashboards

Visualize:
- Configuration change velocity by application
- Secret access patterns by identity
- Failed authentication trends
- Expiring secrets requiring rotation
- Cross-environment configuration drift

### Alerting Configuration

Alert on:
- Any secret access from unexpected IP ranges
- Configuration deletions (immediate alert)
- Secret expiration approaching (30, 14, 7 days)
- Unusual access patterns flagged by Sentinel analytics
- Key Vault throttling (approaching request limits)

---
[Back to Overview](./OVERVIEW.md)
