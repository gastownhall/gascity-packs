# Core Principles

### Private by Default

Session recording captures everything a user sees and does. The default configuration **must mask all text content, block all media elements, and obscure all form inputs** before data leaves the browser. Developers opt **in** to unmasking specific elements known to be safe — never opt **out** of masking elements known to be sensitive. The burden of proof is on the element being safe, not on the element being dangerous. **A missed sensitive element in a permissive configuration is a data breach. A missed safe element in a restrictive configuration is a minor replay quality issue.**

### Consent Before Capture

Session recording is non-essential tracking that requires **explicit, informed, prior consent** under GDPR, ePrivacy Directive, and equivalent regulations. The recording SDK must not initialize, must not attach DOM observers, and must not transmit any data until the user has actively consented to analytics/functional tracking. *"We'll start recording and scrub the PII later"* is not a compliance strategy — it is a violation. The SDK loads after consent, period.

### Data Minimization

Capture only what is necessary to achieve the business objective (debugging, UX analysis, conversion optimization). Recording every page, every session, every user generates massive data volumes with diminishing analytical value and increasing privacy exposure. Use sampling, conditional recording (error-triggered, funnel-specific), and session duration limits to reduce the dataset to what is actually reviewed and acted upon.

### Data Sovereignty

Session recordings contain user behavioral data that constitutes **personal data** under GDPR (online identifiers, behavioral profiles). Where this data is stored, who processes it, and under what legal framework matters. Self-hosted solutions (OpenReplay) keep data within organizational infrastructure. Cloud solutions (FullStory, LogRocket) transfer data to the vendor's infrastructure. The choice must align with the organization's data processing agreements, regulatory obligations, and data residency requirements.

### Zero Secrets in Recordings

Session recordings must **never** capture passwords, credit card numbers, CVVs, social security numbers, authentication tokens, API keys, session cookies, or any other secret material. These values must be masked **client-side before they leave the browser**, not scrubbed server-side after transmission. Client-side masking prevents the data from existing in transit or at rest. Server-side scrubbing attempts to delete data that has already been transmitted — a best-effort cleanup, not a prevention mechanism.

### Foundational Rules

- The session recording SDK initializes only after the user has granted explicit consent for analytics or functional tracking via the consent management platform. **No DOM observation, no event capture, and no network transmission occurs before consent.**
- The default privacy configuration masks all text content and blocks all media elements. Safe elements are explicitly unmasked. Sensitive elements are never unmasked.

---
[Back to Overview](./OVERVIEW.md)
