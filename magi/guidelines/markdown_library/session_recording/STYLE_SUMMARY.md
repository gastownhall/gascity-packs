# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Core | Private by default; consent before capture; data minimization; zero secrets; data sovereignty aligned with regulatory obligations |
| Consent | CMP-gated SDK init; zero requests before consent; explicit opt-in for EU; withdrawal stops recording; documented legal basis in privacy policy; consent records retained 5 years |
| PII Scrubbing | Mask all text by default; mask all inputs; block media; element-level annotation during development; URL sanitization; console sanitization; server-side pattern scrubbing as defense-in-depth |
| Network Sanitization | Strip auth/cookie headers; body capture opt-in only; exclude sensitive API endpoints; field-level redaction on enabled endpoints |
| Key Security | Project keys are public client identifiers; management API keys are server-side secrets; TLS on ingestion; domain restriction; environment-gated initialization; periodic rotation |
| Deployment | Self-hosted for data sovereignty; cloud with DPA/BAA for managed service; verify SOC 2, encryption, sub-processors; per-user deletion capability required |
| Recording Scope | Session sampling (10–25%); error-triggered 100% capture; route exclusion for admin/settings; duration caps; exclude internal users |
| PCI | Exclude payment pages or maximum masking with QSA approval; no keystroke capture on payment routes; no card data in recordings under any configuration |
| HIPAA | BAA with vendor or self-host; mask all PHI; audit access to recordings; maximum masking for healthcare applications |
| Performance | Async SDK load; no CWV regression; batched transmission; disable unused features; monitor CPU/memory impact |
| Retention | 30–180 day defined period; automatic deletion; DSAR deletion workflow; storage capacity planning for self-hosted |
| Access Control | RBAC on dashboard; SSO+MFA; access logging; no raw export; share replay URLs not video files |
| SPA Integration | Client-only initialization; consent-gated in framework plugin; SPA route detection verified; state management plugin with sensitive store exclusion |
| Observability | Session ID propagation to backend; error tracking correlation; backend log integration; support ticket → replay workflow |
| Testing | Staging privacy review with synthetic PII; automated regression testing; quarterly production audit; consent gating verification per browser |
| Shakedown | Real SDK + real ingestion + real storage + real playback; `SHAKEDOWN_PII_TOKEN` absence is binary pass/fail; pass / fail-blocking / fail-nonblocking / inconclusive; four artifacts mandatory |
| Defense in Depth | Redundant capture + fsync + cross-region replication + lifecycle policy + playback validation + checksums + access audit log |
| Rule of Three | Primary store + replica + periodically verified archive — recovery from any two when the third is lost |
| Incident Response | Runbook for PII exposure; immediate recording suspension; scope assessment; deletion of affected recordings; breach assessment within 72 hours |

---
[Back to Overview](./OVERVIEW.md)
