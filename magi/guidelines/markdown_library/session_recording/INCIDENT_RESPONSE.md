# Incident Response for Recording Data

If PII is discovered in session recordings despite masking controls, the organization must respond as a **potential data breach**. The response speed and completeness determine regulatory and reputational impact.

### PII Exposure Runbook

Maintain a runbook for PII exposure in session recordings:

1. **Immediately disable recording** or increase masking to maximum.
2. **Identify the scope** — which pages, which time period, how many recordings affected.
3. **Delete affected recordings** via the platform's API or admin interface.
4. **Assess whether the exposure constitutes a reportable data breach** under GDPR Article 33 (72-hour notification window) or applicable regulation.
5. **Fix the masking configuration**.
6. **Verify the fix in staging**.
7. **Re-enable recording** (after a passing §15 shakedown).

### Automated PII Detection

Configure monitoring for potential PII in recordings:

| Source | Capability |
|:-------|:-----------|
| FullStory | Automated PII detection alerts |
| Sentry | Automated PII detection alerts |
| Self-hosted OpenReplay | Implement custom scanning of stored replay data for PII patterns (email regex, credit card Luhn validation, SSN format) and alert on matches |

Detection enables faster response **before affected recordings are viewed or exported**.

---
[Back to Overview](./OVERVIEW.md)
