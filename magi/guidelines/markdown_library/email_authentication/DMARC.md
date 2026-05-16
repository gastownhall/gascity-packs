# DMARC (Domain-Based Message Authentication, Reporting, and Conformance)

DMARC bridges SPF and DKIM by requiring **domain alignment** (the authenticated domain matches the visible From domain) and providing a **policy** that receiving servers enforce on authentication failures. DMARC also generates aggregate and forensic reports that give domain owners unprecedented visibility into email sent using their domain.

### Minimum Record

Publish a DMARC record at `_dmarc.example.com` as a DNS TXT record. The record must include at minimum:

```dns
v=DMARC1; p=none; rua=mailto:dmarc-agg@example.com
```

Without `rua`, DMARC provides policy but zero visibility.

### Pass Logic

A message passes DMARC if **either** SPF passes with alignment **OR** DKIM passes with alignment. Both are not required. This is why DKIM alignment is critical — when SPF fails due to forwarding, DKIM alignment alone satisfies DMARC.

### DMARC Policy Escalation Path

DMARC deployment follows a mandatory escalation path. Jumping directly to `p=reject` without monitoring is the single most common cause of legitimate email loss during DMARC deployment.

| Phase | Policy | Action |
|:-----:|:-------|:-------|
| 1 — Monitor (4–8 weeks min) | `p=none` with `rua` and `ruf` | Collect aggregate reports. Identify every legitimate sending source: corporate email, marketing ESP, transactional email service, CRM, helpdesk, monitoring alerts, automated notifications. For each source, verify SPF includes and DKIM alignment. Fix misalignments. Do not proceed until aggregate reports show 95%+ pass rate for legitimate mail. |
| 2 — Quarantine (4–8 weeks) | `p=quarantine` with `pct=10` → 25 → 50 → 100 | Monitor for false positives at each step. Investigate every `ruf` (forensic) report for unexpected failures. |
| 3 — Reject | `p=reject` with `pct=10` → 100 | Receiving servers discard (not quarantine) messages that fail both SPF and DKIM alignment. Target state for all domains. Monitor continuously — new sending sources added without DKIM alignment will have their mail rejected. |

### Subdomain Policy

Set the subdomain policy (`sp=`) explicitly if subdomains have different sending profiles than the organizational domain. `sp=reject` on the organizational domain applies to all subdomains that do not publish their own DMARC records. This prevents subdomain spoofing without requiring individual DMARC records on every subdomain.

### Alignment Configuration

- **Relaxed alignment (`adkim=r; aspf=r`)** — default. Organizational domain match; `mail.example.com` aligns with `example.com`.
- **Strict alignment (`adkim=s; aspf=s`)** — exact domain match. Use only when subdomains are independently managed and must not cross-authenticate.

Verify alignment for every third-party sending service. The third-party must either sign with a DKIM key on your domain (custom DKIM), use a Return-Path domain on your domain (custom envelope sender), or both. Default ESP configurations often use the ESP's own domain for DKIM and Return-Path, which fails alignment. Custom domain configuration is required for DMARC compliance.

### DMARC Reporting

- **`rua` (aggregate reports)** — Required on every DMARC record. Daily summaries of authentication results grouped by sending IP. Primary monitoring tool for email authentication health.
- **`ruf` (forensic reports)** — Recommended during monitoring and escalation phases. Headers (and optionally body excerpts) from individual failing messages. Not all receivers generate them; some redact for privacy. Disable or filter in production after `p=reject` if volume is excessive.
- **Dedicated reporting address** — Use an address on a subdomain reserved for DMARC processing (`rua=mailto:dmarc@reports.example.com`). High-volume domains generate thousands of aggregate reports daily. Use a DMARC report processing service (URIports, Postmark DMARC, dmarcian, Valimail) to parse, aggregate, and visualize.
- **External reporting authorization** — If the rua/ruf address is in a different domain than the DMARC record's domain, the receiving domain must publish: `example.com._report._dmarc.reports-domain.com TXT "v=DMARC1"`. Without this, receivers will not send reports.
- **Review cadence** — Weekly during monitoring phases; monthly once at `p=reject`. Look for new unauthorized sending sources (spoofing attempts), legitimate sources with failed alignment (misconfigured third-party services), and drops in overall pass rate.

---
[Back to Overview](./OVERVIEW.md)
