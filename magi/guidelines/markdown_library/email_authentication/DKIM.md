# DKIM (DomainKeys Identified Mail)

DKIM attaches a cryptographic signature to outgoing messages using a private key. The corresponding public key is published as a DNS TXT record under a selector subdomain. Receiving servers verify the signature, confirming the message was authorized by the signing domain and was not altered in transit. DKIM signatures survive forwarding — the signature travels with the message body and signed headers regardless of how many relays the message traverses.

### Key Length and Algorithm

- **2048-bit RSA minimum.** 1024-bit keys are deprecated and vulnerable to factoring attacks with modern compute. Some DNS providers have TXT record length limitations that require splitting 2048-bit keys across multiple strings within a single record — this is normal and handled by DNS resolvers transparently. If the DNS provider cannot accommodate 2048-bit keys, evaluate switching providers.
- **`rsa-sha256` only.** `rsa-sha1` is deprecated (RFC 8301) and must not be used. Receiving servers increasingly reject sha1-signed messages.
- **Ed25519 (RFC 8463) as a secondary algorithm.** Ed25519 keys are smaller (256-bit), faster to verify, and produce shorter signatures. Support is growing but not universal — sign with both RSA-2048 and Ed25519 (dual signing) for maximum compatibility and future-readiness.

### Header Signing

Sign at minimum: `From`, `To`, `Subject`, `Date`, `Message-ID`, `MIME-Version`, `Content-Type`. The `From` header must always be signed — it is the header DMARC uses for alignment. Sign additional headers (`Reply-To`, `In-Reply-To`, `References`, `List-Unsubscribe`) to prevent header manipulation in transit.

### DKIM Alignment

The DKIM signing domain (`d=` value in the signature) must align with the domain in the visible From header. Alignment can be:

- **Relaxed** — organizational domain match (default).
- **Strict** — exact domain match.

Controlled by the DMARC `adkim` tag. Without alignment, the DKIM signature passes verification but does not satisfy DMARC, providing no policy benefit.

### Selector Management

DKIM selectors namespace public keys, enabling multiple keys per domain (different keys for different sending services) and key rotation without downtime.

- Use distinct selectors for each sending service. Marketing email (Mailchimp, SendGrid), transactional email (application servers), and corporate email (Google Workspace, Microsoft 365) each get their own selector and key pair. Compromising one selector does not affect the others.
- Name selectors descriptively: `selector1._domainkey` for the primary ESP, `sendgrid2024._domainkey` for SendGrid, `google._domainkey` for Workspace.
- Include a date or version indicator in selector names to facilitate rotation tracking: `s202601._domainkey`, `google-v2._domainkey`.

### Key Rotation

DKIM private keys, like all cryptographic keys, must be rotated periodically. The rotation process must be seamless — no messages fail DKIM verification during the transition.

- Rotate at least every 6–12 months. Rotate immediately on suspected key compromise.
- Some ESPs (Mailgun, Postmark) support automated rotation. For services requiring manual rotation, schedule calendar reminders and document the process.
- **Overlap method:** publish the new selector's public key in DNS → wait for DNS propagation (verify with `dig`) → switch the signing service to the new private key → verify signed messages pass DKIM with the new selector → remove the old selector's DNS record after a 7–14 day grace period.
- Monitor DKIM pass rates in DMARC aggregate reports during and after rotation. A drop indicates the new key is not propagated, the signing service is still using the old key, or the DNS record is malformed.

### DKIM for Non-Sending Domains

For domains that do not send email, publish a DKIM record with an empty public key (`p=`) at a well-known selector. This explicitly declares no valid signing key exists. Combined with `v=spf1 -all` and DMARC `p=reject`, this creates a comprehensive anti-spoofing posture for parked domains.

---
[Back to Overview](./OVERVIEW.md)
