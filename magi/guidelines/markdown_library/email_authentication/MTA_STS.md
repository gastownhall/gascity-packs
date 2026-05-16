# MTA-STS (Mail Transfer Agent Strict Transport Security)

MTA-STS (RFC 8461) tells sending mail servers that the receiving domain supports TLS and that connections must use TLS with a valid certificate. Without MTA-STS, SMTP encryption is opportunistic — a man-in-the-middle can strip TLS via a downgrade attack, and the sending server will silently fall back to plaintext. MTA-STS makes TLS mandatory for servers that respect the policy.

### Policy File Hosting

Host the policy file at:

```text
https://mta-sts.example.com/.well-known/mta-sts.txt
```

The file specifies:
- `version: STSv1`
- `mode: testing | enforce | none`
- `max_age: <seconds>`
- `mx: <hostname>` (one line per MX hostname)

The HTTPS certificate on `mta-sts.example.com` must be valid — MTA-STS is itself a TLS-based mechanism.

### Testing Mode First

Deploy in `mode: testing` first. Sending servers log failures but still attempt delivery. Monitor TLS-RPT reports for 2–4 weeks to verify all sending servers can connect via TLS with valid certificates. Fix MX hostname mismatches and certificate issues before moving to enforce.

### Enforcement

After testing validates clean TLS connections, switch to `mode: enforce`. Set `max_age` to a long duration (`604800` seconds = 1 week or longer) to cache the policy and reduce repeated DNS lookups.

Update the `id` value in the `_mta-sts` TXT record whenever the policy file changes — the `id` signals to senders that the policy has been updated.

### MX Coordination

List only the actual MX hostnames in the policy file. Wildcards are not supported. If the MX configuration changes (migration to a new email provider):

1. Update the MTA-STS policy file first.
2. Wait for `max_age` to expire, or reduce `max_age` before the migration.
3. Change MX records.

Changing MX records while a cached enforce policy lists the old MX hostnames causes mail delivery failures.

### DANE (DNS-Based Authentication of Named Entities)

DANE (RFC 7671/7672) is an alternative to MTA-STS that uses DNSSEC to publish TLS certificate fingerprints (TLSA records) directly in DNS. DANE provides stronger guarantees than MTA-STS (no TOFU, no CA dependency) but requires DNSSEC on the receiving domain, which limits adoption.

If the domain's DNS zone is DNSSEC-signed, publish TLSA records for each MX hostname. TLSA records bind the MX certificate to the DNS record, preventing CA misissuance and MITM attacks. Sending servers that support DANE (including most major providers) will enforce TLS based on the TLSA record. Maintain TLSA records alongside certificate renewals — a TLSA record pointing to an expired or rotated certificate causes delivery failures.

---
[Back to Overview](./OVERVIEW.md)
