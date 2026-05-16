# Part X: Security and Compliance

This section covers securing Datadog and meeting compliance requirements.

## Data Privacy

### Sensitive Data Scrubbing

Configure automatic scrubbing of sensitive data:

```yaml
# Agent configuration
logs_config:
  processing_rules:
    # Scrub credit card numbers
    - type: mask_sequences
      name: mask_credit_cards
      pattern: '\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b'
      replace_placeholder: "[CREDIT_CARD]"

    # Scrub SSN
    - type: mask_sequences
      name: mask_ssn
      pattern: '\b\d{3}-\d{2}-\d{4}\b'
      replace_placeholder: "[SSN]"

    # Scrub email addresses
    - type: mask_sequences
      name: mask_emails
      pattern: '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
      replace_placeholder: "[EMAIL]"

    # Scrub API keys
    - type: mask_sequences
      name: mask_api_keys
      pattern: '(api[_-]?key|apikey|api_secret)["\s:=]+["\']?([a-zA-Z0-9]{20,})["\']?'
      replace_placeholder: "[API_KEY]"
```

### Application-Level Scrubbing

Scrub before sending to Datadog:

```csharp
public class DatadogScrubber
{
    private static readonly Regex CreditCardRegex = new(
        @"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b",
        RegexOptions.Compiled);

    public string Scrub(string input)
    {
        var result = input;
        result = CreditCardRegex.Replace(result, "[CREDIT_CARD]");
        result = SsnRegex.Replace(result, "[SSN]");
        result = EmailRegex.Replace(result, "[EMAIL]");
        return result;
    }
}
```

### PII in Tags

Never include PII in metric tags:

```csharp
// NEVER DO THIS
DogStatsd.Increment("orders", tags: new[]
{
    $"customer_email:{customer.Email}",      // PII
    $"customer_name:{customer.Name}",        // PII
    $"ip_address:{customer.IpAddress}"       // PII
});

// ACCEPTABLE (anonymized/hashed)
DogStatsd.Increment("orders", tags: new[]
{
    $"customer_id:{customer.Id}",            // Internal ID, not PII
    $"customer_tier:{customer.Tier}",        // Category, not PII
    $"region:{customer.Region}"              // Aggregated location
});
```

## Access Control

### Role-Based Access Control

Configure RBAC for Datadog:

```yaml
roles:
  - name: "Developer"
    permissions:
      - dashboards.read
      - monitors.read
      - logs.read
      - traces.read
    restrictions:
      - env:dev
      - env:staging

  - name: "On-Call Engineer"
    permissions:
      - dashboards.read
      - dashboards.write
      - monitors.read
      - monitors.write
      - logs.read
      - traces.read
      - incidents.write
    restrictions: []  # Full access

  - name: "Security Analyst"
    permissions:
      - logs.read
      - security_monitoring.read
    restrictions:
      - "@security:true"  # Only security-tagged logs

  - name: "Billing Admin"
    permissions:
      - usage.read
      - billing.read
    restrictions: []
```

### API Key Management

```yaml
api_keys:
  - name: "Production Agent"
    permissions: ["submit_metrics", "submit_logs", "submit_traces"]
    restrictions:
      - env:prod

  - name: "CI/CD Pipeline"
    permissions: ["submit_events", "submit_service_checks"]
    restrictions:
      - source:deployment

  - name: "Synthetic Tests"
    permissions: ["submit_synthetics"]
    restrictions: []
```

### Audit Logging

Enable audit logging for compliance:

```yaml
# Datadog audit events to track
audit_events:
  - user_login
  - user_logout
  - api_key_created
  - api_key_revoked
  - monitor_created
  - monitor_modified
  - dashboard_created
  - dashboard_modified
  - role_assignment_changed
```

## Compliance Frameworks

### SOC 2 Requirements

| Requirement       | Datadog Implementation                  |
|-------------------|-----------------------------------------|
| Access Control    | RBAC, SSO, MFA                          |
| Audit Logging     | Audit trail of all actions              |
| Data Encryption   | TLS in transit, encrypted at rest       |
| Incident Response | Alerting, incident management           |
| Change Management | Deployment tracking, monitor versioning |

### GDPR Requirements

| Requirement         | Datadog Implementation            |
|---------------------|-----------------------------------|
| Data Minimization   | Log sampling, data scrubbing      |
| Right to Access     | Export user-related logs          |
| Right to Deletion   | Retention policies, data deletion |
| Data Protection     | Encryption, access control        |
| Breach Notification | Security monitoring, alerting     |

### HIPAA Requirements

| Requirement           | Datadog Implementation          |
|-----------------------|---------------------------------|
| Access Controls       | RBAC, audit logging             |
| Audit Controls        | Comprehensive audit trail       |
| Integrity Controls    | Data validation, checksums      |
| Transmission Security | TLS encryption                  |
| PHI Protection        | Scrubbing rules, no PHI in logs |

## Security Monitoring

### Security Signals

Configure security detection rules:

```yaml
security_rules:
  - name: "Brute Force Login Attempt"
    query: |
      @evt.name:authentication.failure
      | stats count by @usr.id
      | filter count > 10
    timeframe: "5m"
    severity: "high"

  - name: "Privilege Escalation"
    query: |
      @evt.name:authorization.success
      @action:admin_access
      -@usr.role:admin
    severity: "critical"

  - name: "Unusual Data Access"
    query: |
      @evt.name:data.access
      @data.classification:sensitive
      | anomalies
    severity: "medium"
```

### Threat Detection Dashboard

```yaml
dashboard:
  title: "Security Overview"
  widgets:
    - title: "Failed Logins"
      query: "sum:security.authentication.failures{*} by {source}"

    - title: "Privilege Escalation Attempts"
      query: "sum:security.authorization.failures{*} by {user}"

    - title: "Anomalous Data Access"
      query: "count:security.data_access{anomaly:true} by {user,resource}"

    - title: "Security Signals"
      type: "security_signals_stream"
```

---
[Back to Overview](./OVERVIEW.md)
