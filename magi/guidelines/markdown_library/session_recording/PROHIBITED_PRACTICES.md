# Prohibited Practices

### Never Do

- Initialize the recording SDK before the user has granted explicit consent. **Consent must precede capture.**
- Configure the SDK with default masking disabled (`maskAllText: false`, Private by Default off).
- Unmask password fields, credit card fields, SSN fields, or authentication token fields under any circumstance.
- Capture `Authorization`, `Cookie`, `Set-Cookie`, or API key headers in network request recordings.
- Enable request/response body capture by default.
- Embed management API keys, admin tokens, or server-side credentials in client-side code alongside the recording SDK.
- Record sessions on payment pages without maximum masking and PCI QSA approval.
- Record sessions in healthcare applications without maximum masking and a BAA with the recording vendor.
- Retain session recordings indefinitely.
- Download or export raw session recordings to local machines, shared drives, or communication channels.
- Deploy recording to production without testing masking configuration in staging with synthetic PII.
- Record internal employee sessions without explicit justification and scope limitation.
- Deploy session recording without documenting it in the privacy policy with specifics on what is recorded and why.
- Initialize the recording SDK on the server in SSR frameworks. **The SDK is client-only.**
- Skip the §15 shakedown after a triggering change.
- Run the shakedown against a mocked SDK, ingestion endpoint, or storage backend.
- Drive the shakedown with real user data copied from production.

---
[Back to Overview](./OVERVIEW.md)
