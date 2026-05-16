# Email Authentication and Anti-Spoofing Library

This directory contains an expanded, modularized version of the Email Authentication and Anti-Spoofing Guidelines. Apply universally to every domain the organization owns and every service authorized to send email on its behalf.

## Critical Mandates (Read First)
- **Authentication Is Mandatory, Not Optional** — Gmail, Yahoo, Microsoft, and Apple enforce auth requirements as of 2024–2025.
- **DKIM Is the Backbone** — survives forwarding where SPF fails.
- **DMARC Is the Enforcer** — without DMARC, receiving servers make ad-hoc decisions.
- **Every Domain, Every Subdomain** — attackers spoof the domains you forgot about.
- **Monitor Before You Enforce** — `p=none` with reporting → analyze 4-8 weeks → escalate.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Mandatory authentication, DKIM backbone, DMARC enforcer, every domain, monitor-then-enforce, foundational rules.
2. [SPF (Sender Policy Framework)](./SPF.md) — Single record, qualifier selection, 10 DNS lookup limit, mechanism selection, HELO/EHLO, quarterly audit.
3. [DKIM (DomainKeys Identified Mail)](./DKIM.md) — Key length, header signing, alignment, selector management, key rotation, non-sending domains.
4. [DMARC](./DMARC.md) — Minimum record, pass logic, escalation path, subdomain policy, alignment, reporting.
5. [Third-Party Sender Alignment](./THIRD_PARTY_SENDERS.md) — Sender inventory, custom DKIM, custom Return-Path, onboarding/offboarding.
6. [BIMI (Brand Indicators)](./BIMI.md) — Prerequisites, logo format, self-asserted record, VMC/CMC certificates.
7. [MTA-STS](./MTA_STS.md) — Policy file, testing mode, enforcement, MX coordination, DANE.
8. [TLS-RPT](./TLS_RPT.md) — Record, reporting address, sequence with MTA-STS.
9. [ARC (Authenticated Received Chain)](./ARC.md) — Outbound, inbound, triage pattern.
10. [Parked and Non-Sending Domain Protection](./PARKED_DOMAINS.md) — Required record set, monitoring, non-sending subdomains.
11. [DNS Management for Email Records](./DNS_MANAGEMENT.md) — Validation, TTL strategy, propagation verification, version control, DNSSEC.
12. [Shakedown — End-to-End Authentication Validation](./SHAKEDOWN.md) — Definition, triggers, validation requirements, sequences, artifacts, anti-patterns.
13. [Monitoring and Incident Response](./MONITORING_INCIDENT.md) — Aggregate report processing, reputation monitoring, alerting, runbook.
14. [Deliverability Best Practices](./DELIVERABILITY.md) — Complaint rate, stream separation, FCrDNS, one-click List-Unsubscribe.
15. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
16. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do list.
17. [Required Practices](./REQUIRED_PRACTICES.md) — Always Do list.
18. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
