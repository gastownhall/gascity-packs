# Required Practices

### Always Do

- Gate SDK initialization behind CMP consent for analytics/functional tracking. **Zero network requests before consent.**
- Enable maximum masking by default: mask all text, block all media, obscure all inputs. Unmask selectively.
- Mask all form inputs by default. Selectively unmask only non-sensitive fields with documented justification.
- Sanitize URLs to strip PII-containing query parameters and tokens before recording.
- Strip authorization and authentication headers from captured network requests.
- Sanitize or disable console log capture.
- Load the SDK asynchronously. Verify no Core Web Vitals regression via Lighthouse and RUM.
- Restrict SDK project keys to authorized domains where the vendor supports domain restrictions.
- Enforce HTTPS on all recording data ingestion endpoints. **No plaintext transmission of replay data.**
- Define and enforce a retention period (30–180 days). Configure automatic deletion.
- Implement DSAR access and deletion workflows for session recording data.
- Restrict recording platform access by role. Enforce SSO and MFA.
- Log access to individual session recordings with viewer identity and timestamp.
- Test masking configuration in staging with synthetic PII before every production deployment.
- Conduct quarterly manual audits of production recordings for PII exposure.
- Document session recording specifics in the privacy policy: what, why, who, how long, and user rights.
- Integrate session replay with error tracking for direct error-to-replay correlation.
- Run a §15 shakedown after every triggering change, with full artifact capture.

---
[Back to Overview](./OVERVIEW.md)
