# Style Summary

| Element | Required Style |
|:--------|:---------------|
| **SPF** | `~all` for sending domains with DMARC; `-all` for non-sending only; stay under 10 lookups; no `ptr`; no `+all`; audit quarterly; flatten or macro when approaching limit |
| **DKIM** | 2048-bit RSA minimum; `rsa-sha256` only; sign From header always; distinct selectors per service; rotate every 6–12 months via overlap method; align `d=` to From domain |
| **DMARC** | Deploy at `p=none` with `rua` first; escalate via `pct` through quarantine to reject; `sp=` for subdomains; relaxed alignment default; process aggregate reports automatically; review weekly during escalation, monthly at enforcement |
| **BIMI** | Requires DMARC enforcement; SVG Tiny P/S format; HTTPS-hosted logo; self-asserted for Yahoo/Fastmail; VMC (trademarked) or CMC (non-trademarked) for Gmail; annual certificate renewal |
| **MTA-STS** | Policy file at `mta-sts.example.com`; testing mode first; monitor via TLS-RPT; enforce after clean reports; update policy `id` on changes; coordinate with MX migrations |
| **TLS-RPT** | Publish before MTA-STS enforcement; dedicated reporting address; JSON reports from senders; monitor for TLS negotiation failures and certificate errors |
| **ARC** | Enable on outbound gateways that modify messages; preserves auth results across forwarding; trusted by Gmail, Microsoft, Yahoo |
| **Parked Domains** | SPF `-all`; DMARC `p=reject`; null MX; DKIM empty key; include in monitoring pipeline; every owned domain covered |
| **Third-Party Senders** | Sender inventory maintained; custom DKIM per ESP; custom Return-Path where possible; configure auth before sending; remove records on offboarding |
| **DNS** | Validate syntax before publish; short TTL during changes; verify propagation; version-control zone files; enable DNSSEC where supported |
| **Shakedown** | Real sending infrastructure; controlled receiver exposing `Authentication-Results`; verify pass AND alignment; capture artifacts; classify outcome |
| **Monitoring** | Automated DMARC analytics; Google Postmaster Tools; blocklist monitoring; alert on pass rate drops; alert on spoofing spikes; incident runbook maintained |
| **Deliverability** | Complaint rate below 0.1%; stream separation via subdomains; FCrDNS on sending IPs; one-click List-Unsubscribe; authentication necessary but not sufficient |
| **Defense in Depth** | SPF + DKIM + DMARC + MTA-STS/TLS-RPT + BIMI + inbox-placement monitoring + bounce/complaint feedback |
| **Rule of Three** | A message MUST pass at least two of {SPF, DKIM, DMARC alignment} to be considered authentic |

---

Following these rules produces email authentication infrastructure that survives forwarding, resists spoofing, gets reliably delivered, and provides the visibility to detect drift before it causes outages. Every domain publishes the canonical triple. Every sending service is aligned. Every change is shaken down end-to-end before it goes live.

**Apply this guidance universally to every domain the organization owns and every service authorized to send email on its behalf.**

---
[Back to Overview](./OVERVIEW.md)
