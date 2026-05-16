# Session Recording and Replay Library

**Scope:** All web properties and applications that deploy session recording tools — OpenReplay (self-hosted and cloud), FullStory, Sentry Session Replay, LogRocket, Microsoft Clarity, Hotjar, Datadog RUM Session Replay, Mouseflow, and any future recording tool. Applies to traditional server-rendered sites and headless SPA frontends (Nuxt, Next.js, React).

**Runtime:** OpenReplay Tracker 14+, FullStory 2.x, Sentry SDK 8+, LogRocket 7+. Compliance scope: GDPR / ePrivacy Directive, CCPA/CPRA, PCI DSS 4.0, SOC 2 Type II, HIPAA where applicable.

## Critical Mandates (Read First)
- **Private by Default** — mask all text, block all media, obscure all inputs; opt-in to unmasking.
- **Consent Before Capture** — zero network requests before user grants consent.
- **Data Minimization** — sample, conditionally record, cap duration.
- **Zero Secrets in Recordings** — client-side masking before data leaves the browser.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Consent Management](./CONSENT_MANAGEMENT.md)
3. [PII Scrubbing and Data Masking](./PII_SCRUBBING.md)
4. [SDK Key and Configuration Security](./SDK_KEY_SECURITY.md)
5. [Self-Hosted vs Cloud Deployment](./SELF_HOSTED_VS_CLOUD.md)
6. [Recording Scope and Sampling](./RECORDING_SCOPE.md)
7. [PCI DSS and Payment Page Handling](./PCI_DSS.md)
8. [HIPAA and Healthcare Considerations](./HIPAA.md)
9. [Performance Impact](./PERFORMANCE.md)
10. [Data Retention and Deletion](./RETENTION_DELETION.md)
11. [Access Control and Internal Governance](./ACCESS_CONTROL.md)
12. [SPA and Framework Integration](./SPA_INTEGRATION.md)
13. [Observability Integration](./OBSERVABILITY.md)
14. [Testing and Validation](./TESTING.md)
15. [Shakedown — Record→Upload→Playback Validation](./SHAKEDOWN.md)
16. [Incident Response for Recording Data](./INCIDENT_RESPONSE.md)
17. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
18. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
19. [Required Practices](./REQUIRED_PRACTICES.md)
20. [Style Summary](./STYLE_SUMMARY.md)
