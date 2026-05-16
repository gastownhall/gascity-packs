# Testing and Validation

Privacy configuration must be tested, not assumed. A masking rule that works for simple text may fail for dynamically rendered content, shadow DOM components, or third-party widgets. **Validation must be ongoing, not a one-time check.**

### Staging Privacy Review

Conduct a privacy review of session recordings in a staging environment **before enabling recording in production**. Record test sessions with realistic (but synthetic) PII. Review the replays to verify:

- All form inputs are masked.
- User-generated content is masked.
- Media elements are blocked.
- URLs are sanitized.
- Network request headers are stripped.
- Console output is filtered.

**Any visible PII in the replay is a configuration defect that must be fixed before production deployment.**

### Automated Privacy Regression

After every frontend deployment, record a test session that interacts with known PII-containing elements and verify the replay does not expose PII:

1. Initialize the recording SDK (Playwright or Cypress).
2. Fill in forms with test PII.
3. Capture the session.
4. Retrieve the replay via the recording platform's API.
5. Assert the PII is masked in the replay data.

### Quarterly Manual Audits

Schedule quarterly manual privacy audits of production recordings:

- Sample 20–50 recordings from different pages and user flows.
- Review for PII exposure, unmasked sensitive fields, leaked tokens in URLs or network requests, and visible personal information in dynamic content.
- Document findings, remediate, and re-test.

### Consent Gating Verification

Verify consent gating by testing with a clean browser (no prior consent):

1. Load the application.
2. Verify via browser DevTools (Network tab) that **zero requests** are made to the recording platform's domain before consent is granted.
3. Grant consent and verify recording starts.
4. Revoke consent and verify recording stops.

This test must pass for every supported browser and device type.

---
[Back to Overview](./OVERVIEW.md)
