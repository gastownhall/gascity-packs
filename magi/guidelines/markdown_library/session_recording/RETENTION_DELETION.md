# Data Retention and Deletion

Session recordings are personal data with a finite useful life. Retention policies balance analytical utility against storage cost, privacy exposure, and regulatory obligations. The **GDPR storage limitation principle** (Article 5(1)(e)) requires that personal data be kept only as long as necessary.

### Retention Periods

| Purpose | Range |
|:--------|:------|
| Debugging | 30 days |
| UX analysis and funnel optimization | 90 days |
| Longitudinal studies (maximum) | 180 days |

**Configure automatic deletion at the end of the retention period. Do not retain recordings indefinitely. Document the retention period in the privacy policy.**

### Data Subject Access and Deletion (DSAR)

Implement DSAR and deletion request workflows. When a user exercises their right to erasure (GDPR Article 17) or deletion (CCPA), all session recordings for that user must be identified and deleted **within the regulatory timeframe (typically 30 days)**:

- Query recordings by user identifier.
- If users are anonymous, deletion by session ID or cookie ID is the fallback.

### Self-Hosted Retention Enforcement

For self-hosted deployments, automate retention enforcement via cron or scheduled jobs that purge recordings older than the retention period. **Monitor storage consumption** — session recordings accumulate rapidly. A high-traffic site recording 25% of sessions at 90-day retention can consume terabytes of storage. Plan capacity accordingly.

---
[Back to Overview](./OVERVIEW.md)
