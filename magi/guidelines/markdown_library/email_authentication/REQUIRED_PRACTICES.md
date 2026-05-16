# Required Practices

### Always Do

- Publish SPF records on every domain. `~all` for sending domains, `-all` for non-sending domains.
- Use 2048-bit RSA DKIM keys minimum. Sign with `rsa-sha256`. Sign the From header.
- Use distinct DKIM selectors per sending service. Never share keys across services.
- Align DKIM signing domain with the visible From header domain for DMARC compliance.
- Rotate DKIM keys every 6–12 months using the overlap method.
- Publish DMARC records with `rua` reporting on every domain.
- Follow the escalation path: `p=none` (monitor) → `p=quarantine` (enforce gradually) → `p=reject` (full enforcement).
- Set `sp=` on organizational domain DMARC records to protect subdomains.
- Maintain a documented inventory of all authorized sending services with alignment status.
- Configure custom DKIM on every third-party ESP. Verify alignment before sending.
- Protect all non-sending domains with SPF `-all`, DMARC `p=reject`, and null MX records.
- Process DMARC aggregate reports automatically with analytics tooling.
- Publish TLS-RPT records and monitor TLS delivery health before MTA-STS enforcement.
- Maintain spam complaint rates below 0.1%. Implement one-click List-Unsubscribe.
- Validate DNS record syntax before publication. Verify propagation after changes.
- Run a shakedown after every change to a sender identity, DKIM selector, DMARC policy, MX, or security gateway.

---
[Back to Overview](./OVERVIEW.md)
