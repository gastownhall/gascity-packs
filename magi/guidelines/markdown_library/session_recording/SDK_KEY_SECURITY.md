# SDK Key and Configuration Security

Session recording SDKs require a project key or organization ID for initialization. These keys appear in client-side JavaScript — they are visible in the page source, browser DevTools, and any script bundle. The security model must account for this exposure.

### Key Classification

| Key type | Visibility | Risk |
|:---------|:-----------|:-----|
| Project key (OpenReplay `projectKey`, FullStory `orgId`, Sentry DSN) | Public client-side identifier | Leaked key allows fake session injection — poisons analytics |
| Management API key | **Server-side secret** | Grants admin access; never include in frontend bundles |

**Never** embed server-side API keys, admin tokens, or management API credentials in client-side code alongside the recording SDK. The management API key (used for deleting recordings, managing projects, querying sessions programmatically) must never appear in frontend bundles, HTML source, or environment variables prefixed with `NEXT_PUBLIC_` or `VITE_`.

### TLS Enforcement

For OpenReplay self-hosted deployments, secure the ingestion endpoint with **TLS**. Without TLS, recording data — including any PII that survived masking — traverses the network in plaintext. The ingestion endpoint must be HTTPS. Configure HSTS on the OpenReplay domain.

### Environment Restriction

Restrict the recording SDK initialization to specific environments:

| Environment | Initialize? |
|:------------|:------------|
| Local development | **No** — developers may interact with test accounts containing realistic PII |
| Staging connected to production data | **No** |
| Isolated staging with synthetic data | Yes |
| Production | Yes |

Use environment checks (`import.meta.env.PROD`, `process.env.NODE_ENV === 'production'`) to conditionally load the SDK.

### Key Rotation

Rotate SDK project keys periodically (annually or on suspected abuse):

1. Regenerate the key in the recording platform.
2. Update the frontend configuration.
3. Deploy.
4. Verify recordings appear in the new project.
5. Monitor for data arriving on the old key after rotation and investigate.

### Domain Restrictions

Restrict the SDK project key to specific domains where the SDK vendor supports domain restrictions. For self-hosted OpenReplay, restrict the ingestion endpoint to the application's domain via CORS and network-level access control. Block direct access to the ingestion API from unauthorized origins.

---
[Back to Overview](./OVERVIEW.md)
