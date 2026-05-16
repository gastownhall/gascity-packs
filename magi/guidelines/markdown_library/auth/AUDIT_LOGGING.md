# Audit Logging and Monitoring

Authentication and authorization events are the highest-value security logs in any system. They detect compromised accounts, unauthorized access attempts, and permission abuse.

### Required Authentication Events

Log all of:
- Successful logins
- Failed logins
- Logouts
- Token issuance / refresh / revocation
- MFA challenges and failures
- Password changes
- Account lockouts

Required fields per event: timestamp, user identifier (not password), source IP, user agent, result.

### Required Authorization Failures

Log access-denied events with:
- Requested resource
- Required permission
- User identity
- Timestamp

### Anomaly Alerting

Alert on:
- Multiple failed logins from same IP (brute force)
- Successful login from a new geographic location (account takeover)
- Simultaneous sessions from geographically distant locations (credential sharing or theft)
- Privilege escalation events (role changes, permission grants)

### Log Integrity

- Write logs to **append-only storage** or a centralized SIEM that the application cannot modify.
- An attacker who compromises the application and can delete auth logs erases the evidence of their intrusion.

### Never Log Credentials

**Never log credentials, tokens, session IDs, API keys, or secrets** in audit logs. Log the event type and user identity, not the authentication material itself. A leaked audit log must not become a credential store.

---
[Back to Overview](./OVERVIEW.md)
