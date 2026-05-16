# DNSSEC

### DNSSEC Purpose

DNSSEC adds cryptographic signatures to DNS responses, enabling resolvers to verify that a response was not tampered with between the authoritative server and the client. It prevents DNS spoofing and cache poisoning attacks by establishing a chain of trust from the DNS root zone down to the individual record level.

DNSSEC does not encrypt DNS queries — it authenticates them. Privacy-focused DNS encryption (DoH, DoT) addresses query confidentiality; DNSSEC addresses response integrity. They are complementary, not overlapping.

### DNSSEC Key Types

| Key | Role |
|:----|:-----|
| Zone Signing Key (ZSK) | Signs individual record sets within the zone; rotated every 1–3 months; smaller key size for computational efficiency |
| Key Signing Key (KSK) | Signs the ZSK; rotated every 1–2 years; longer key size for stronger security; changes require DS record update at the registrar |
| Delegation Signer (DS) | Hash of the KSK published in the parent zone (e.g., at the TLD level); submitted to the registrar when enabling DNSSEC and updated during KSK rollovers |

### DNSSEC Algorithm Selection

Use **Algorithm 13 (ECDSA P-256 with SHA-256)** for new deployments. It produces smaller signatures than RSA-based algorithms, reducing DNS response size and improving performance. **Algorithm 8 (RSA/SHA-256)** is acceptable for legacy compatibility.

Forbidden:
- Algorithm 5 (RSA/SHA-1) — SHA-1 is cryptographically deprecated.
- Algorithm 7 (RSASHA1-NSEC3-SHA1) — SHA-1 is cryptographically deprecated.

### Enabling DNSSEC

Enable DNSSEC on all domains and verify the chain of trust immediately after enabling. A misconfigured DNSSEC deployment is worse than no DNSSEC — if the DS record at the registrar does not match the KSK at the authoritative server, validating resolvers return SERVFAIL and the domain becomes unreachable for users behind validating resolvers (which includes most major public resolvers: Google, Cloudflare, Quad9).

| Provider Combination | Steps |
|:---------------------|:------|
| Cloudflare DNS | One-click activation in DNS settings; Cloudflare manages ZSK and KSK automatically; add the DS record Cloudflare provides to the registrar (automatic if domain is also at Cloudflare Registrar) |
| GoDaddy with GoDaddy nameservers | Automatic activation; GoDaddy handles signing and DS record publication; no manual key management |
| GoDaddy with external nameservers | Manually add the DS record from your DNS provider to GoDaddy's DNSSEC management interface — key tag, algorithm, digest type, and digest value exactly as specified |

Test DNSSEC validation immediately after enabling using `dnsviz.net` or Verisign's DNSSEC Debugger. Monitor for validation failures continuously.

### DNSSEC Key Rollover

ZSK rollovers are routine and typically automated by the DNS provider. KSK rollovers require updating the DS record at the registrar. The rollover process follows a double-DS or double-KSK pattern:

1. Publish the new DS record alongside the old one.
2. Wait for propagation (at least 2× the DS record TTL).
3. Remove the old DS record.

Removing the old DS before the new one has fully propagated breaks the chain of trust. Choose a DNS provider that automates key management — manual key rollovers introduce human error that can take down DNS resolution for the entire domain.

---
[Back to Overview](./OVERVIEW.md)
