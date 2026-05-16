# Core Principles

These guidelines define strict conventions for email authentication across all organizational domains, covering SPF record architecture, DKIM key management, DMARC policy escalation, BIMI brand indicator deployment, MTA-STS transport security, TLS-RPT reporting, ARC chain validation, parked domain protection, third-party sender alignment, and ongoing monitoring for deliverability and anti-abuse compliance.

**Scope:** All domains owned or operated by the organization — primary domains, subdomains, parked domains, and domains delegated to third-party email service providers (ESPs). Applies to transactional email, marketing email, internal email, and automated system notifications.

**Runtime references:** SPF (RFC 7208), DKIM (RFC 6376), DMARC (RFC 7489), BIMI (AuthIndicators Working Group), MTA-STS (RFC 8461), TLS-RPT (RFC 8460), ARC (RFC 8617).

### Authentication Is Mandatory, Not Optional

As of 2024–2025, Gmail, Yahoo, Microsoft, and Apple enforce email authentication requirements for all senders. Bulk senders (5,000+ messages/day) must implement SPF, DKIM, and DMARC. Non-bulk senders must implement at least SPF or DKIM. Unauthenticated mail is increasingly rejected, quarantined, or spam-foldered regardless of content quality. Authentication is the price of admission to the inbox.

### DKIM Is the Backbone

DKIM survives email forwarding, mailing list redistribution, and relay chains where SPF fails. DKIM provides both authorization (the signer authorized the message) and integrity (the message was not modified in transit). Invest more in DKIM alignment and key management than in SPF complexity. When one mechanism must carry authentication through indirect mail flows, DKIM is the one that works.

### DMARC Is the Enforcer

SPF and DKIM authenticate. DMARC decides what happens when authentication fails. Without DMARC, receiving servers make their own ad-hoc decisions about failed authentication — decisions that vary by provider and change without notice. DMARC provides a deterministic, domain-owner-controlled policy for handling authentication failures and generates reports that provide visibility into who is sending as your domain.

### Every Domain, Every Subdomain

Attackers spoof the domains you forgot about. Every domain the organization owns — active, parked, legacy, defensive registration — publishes SPF, DKIM (with no keys for non-senders), and DMARC. Every subdomain either inherits the organizational domain's DMARC policy or publishes its own. A single unprotected subdomain undermines the trust built by the primary domain.

### Monitor Before You Enforce

DMARC enforcement (`p=quarantine` or `p=reject`) without adequate monitoring causes legitimate email to silently disappear. The deployment path is always: publish at `p=none` with reporting → analyze aggregate reports for 4–8 weeks → identify and fix all legitimate sending sources → escalate enforcement progressively. Skipping monitoring is the most common cause of email authentication disasters.

### Foundational Rules

- Every domain and subdomain that the organization owns publishes SPF, DKIM, and DMARC records in DNS. No exceptions for "unused" domains — unused domains are the most attractive spoofing targets.
- DMARC is the policy layer. SPF and DKIM are authentication mechanisms that feed into DMARC. Do not rely on SPF alone or DKIM alone as security controls. The three protocols form a system; removing any one weakens the others.

---
[Back to Overview](./OVERVIEW.md)
