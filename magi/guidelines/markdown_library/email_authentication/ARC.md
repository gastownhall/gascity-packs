# ARC (Authenticated Received Chain)

ARC (RFC 8617) preserves email authentication results across intermediaries (mailing lists, forwarding services, security gateways) that modify messages in ways that break DKIM and SPF. ARC allows the final receiving server to trust the authentication results from earlier hops in the chain, even when the intermediary re-signed or modified the message.

### Outbound

Enable ARC signing on all outbound email gateways that modify messages (content filters, DLP systems, email security gateways, mailing list managers). ARC seals the authentication results at each hop, creating a chain of custody that downstream DMARC evaluators can trust. Gmail, Microsoft 365, and Yahoo honor ARC chains from trusted sealers.

### Inbound

When receiving, configure DMARC evaluation to consider ARC results (`arc=pass`) for messages from trusted ARC sealers. This prevents legitimate mailing list traffic and forwarded messages from being rejected by DMARC enforcement when SPF and DKIM break due to intermediary modification.

### Triage Pattern

Monitor DMARC forensic reports for messages failing DMARC due to forwarding or mailing list modification. These are candidates for ARC-based rescue. If aggregate reports show a consistent pattern of DMARC failures from known legitimate forwarding sources, ARC integration on those sources resolves the failures without weakening DMARC policy.

---
[Back to Overview](./OVERVIEW.md)
