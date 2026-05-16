# SPF (Sender Policy Framework)

SPF publishes a DNS TXT record listing IP addresses and hostnames authorized to send email for a domain. Receiving servers check the envelope sender (MAIL FROM / Return-Path) against the SPF record. SPF has inherent limitations — it breaks on forwarding, is constrained to 10 DNS lookups, and does not protect the visible From header without DMARC alignment.

### Single Record Per Domain

Publish exactly one SPF record per domain/subdomain. Multiple SPF records (multiple TXT records starting with `v=spf1`) cause a `PermError` that fails SPF evaluation entirely. Merge all sending sources into a single record.

### Qualifier Selection

| Qualifier | Use Case |
|:----------|:---------|
| `~all` (softfail) | **Required** for domains that send email. Per RFC 7489 §10.1 and M3AAWG best practices, `-all` (hardfail) can cause receiving servers to reject messages at the SMTP layer before DKIM and DMARC evaluation occurs. With DMARC at `p=reject`, `~all` provides identical security to `-all` because DMARC treats both as SPF failures. `~all` preserves the opportunity for DKIM to rescue forwarded messages that SPF cannot authenticate. |
| `-all` (hardfail) | **Required** for domains that send no email whatsoever (parked domains, defensive registrations): `v=spf1 -all`. This is the strongest signal that no legitimate mail originates from the domain. |
| `+all` | **Forbidden.** Authorizes every IP address on the internet to send as the domain. Worse than no SPF record. |

### 10 DNS Lookup Limit

Stay within the 10 DNS lookup limit (RFC 7208 §4.6.4). Each `include`, `a`, `mx`, `ptr`, `exists`, and `redirect` mechanism that requires DNS resolution counts toward the limit. `ip4` and `ip6` mechanisms do not count. Exceeding 10 lookups causes a `PermError` that fails SPF for all messages. Monitor lookup count after every record change.

When approaching the limit:

- Use SPF macros (`%{i}`, `%{d}`) for dynamic expansion without additional DNS lookups.
- Use SPF flattening tools that resolve include chains to `ip4`/`ip6` literals at publish time. Re-flatten on a schedule or via webhook from a DNS management tool when upstream provider IPs change.

### Mechanism Selection

- **Avoid `ptr`** — RFC 7208 §5.5 explicitly recommends against its use due to performance (reverse DNS lookups) and reliability (reverse DNS often misconfigured) concerns. Use `ip4`, `ip6`, and `include` instead.
- **Avoid broad CIDR ranges** — Authorizing an entire `/16` or `/24` when only a single IP sends mail over-authorizes and weakens SPF's protection. Authorize the narrowest range possible. Use DMARC aggregate reports to identify the actual sending IPs and refine the record.

### HELO/EHLO Coverage

Publish SPF records for both the RFC5321.MailFrom domain (envelope sender) and the EHLO/HELO domain. Most SPF guidance focuses on MAIL FROM, but the HELO identity is also checked. Ensure the server's HELO hostname has a valid SPF record or at minimum resolves to the server's IP via A/AAAA records.

### Quarterly Audit

Audit SPF records quarterly. Remove `include` mechanisms for services no longer in use. Unused includes waste lookup budget and authorize servers that may be compromised or repurposed. DMARC aggregate reports reveal which SPF sources are actively sending — sources absent from reports for 90+ days are candidates for removal.

---
[Back to Overview](./OVERVIEW.md)
