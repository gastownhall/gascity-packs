# API Authentication Patterns

API authentication varies by consumer type:
- First-party frontends → session cookies or short-lived tokens
- Third-party integrations → API keys or OAuth client credentials
- Inter-service calls → mutual TLS or service tokens

### API Keys

- **API keys are authentication, not authorization.** A key identifies the caller. Rate limits, resource access, and feature flags are separate decisions.
- **Transmit in headers** (`X-API-Key` or `Authorization`), **never in URL query parameters.** URLs appear in server logs, browser history, referrer headers, and proxy logs.
- **Hash API keys before storage** (SHA-256 is sufficient since API keys are high-entropy). Store only the hash. Display the full key once at creation. On request, hash the presented key and compare. Prevents disclosure from a database breach.
- Implement per-key rate limiting and usage tracking. Provide owners with usage dashboards. Alert on anomalous patterns.

### Service-to-Service

For microservice architectures:
- **mutual TLS (mTLS)** — service mesh implementations (Istio, Linkerd) automate this between services
- **Short-lived service tokens** issued by an internal token service — shortest practical lifetime (5-15 minutes), scoped to specific service pairs

---
[Back to Overview](./OVERVIEW.md)
