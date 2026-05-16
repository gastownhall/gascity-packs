# Prohibited Practices

### Never Do

- Operate any domain without SPF, DKIM, and DMARC records. Every domain publishes all three.
- Use `+all` in SPF records — authorizes the entire internet as a sender.
- Use `-all` on domains that actively send email when DMARC is deployed. Use `~all` for sending domains; `-all` for non-sending domains only.
- Exceed 10 DNS lookups in SPF records — `PermError` fails SPF for all messages.
- Use 1024-bit DKIM keys. 2048-bit RSA is the minimum.
- Sign with `rsa-sha1`. Use `rsa-sha256` exclusively.
- Deploy DKIM without aligning the `d=` domain to the visible From header. Unaligned DKIM does not satisfy DMARC.
- Deploy DMARC at `p=reject` without monitoring at `p=none` first. Monitoring identifies legitimate sending sources before enforcement silences them.
- Publish DMARC records without `rua` reporting tags — DMARC without reporting is enforcement without visibility.
- Leave parked, unused, or defensive domains without email authentication records. Unprotected domains are spoofing targets.
- Use the same DKIM key pair across multiple sending services. Compromise of one service compromises all services sharing the key.
- Leave `include` mechanisms for decommissioned services in SPF records. Wastes lookup budget and authorizes servers no longer under your control.
- Publish BIMI records without DMARC enforcement (`p=quarantine` or `p=reject`). Providers ignore BIMI without enforcement.
- Rely on manual XML parsing for DMARC aggregate report analysis at scale.

---
[Back to Overview](./OVERVIEW.md)
