# Email DNS Records

### SPF

SPF declares which servers are authorized to send email for the domain. Published as a TXT record at the domain apex.

```dns
v=spf1 include:_spf.google.com include:sendgrid.net -all
```

- Use `-all` (hard fail) for production domains — rejects messages from unauthorized senders.
- Use `~all` (soft fail) only during migration or testing.
- SPF has a **10 DNS lookup limit** — each `include`, `a`, `mx`, and `redirect` mechanism counts as one lookup. Exceeding 10 causes SPF `permerror`. Flatten SPF records or use a third-party SPF flattening service if you approach the lookup limit.

### DKIM

DKIM signs outgoing messages with a private key; receivers verify the signature against a public key published in DNS as a TXT record under `selector._domainkey.example.com`.

- Configure DKIM for every service that sends email on behalf of the domain.
- Each email service (Google Workspace, Microsoft 365, SendGrid, Mailgun) provides its own DKIM selector and public key.
- DKIM keys are long — often exceeding the 255-character TXT record string limit. Split the key across multiple quoted strings within a single TXT record.
- Verify the published key with `dig TXT selector._domainkey.example.com`.

### DMARC

DMARC ties SPF and DKIM together with a policy and reporting mechanism. Published as a TXT record at `_dmarc.example.com`.

```dns
v=DMARC1; p=reject; rua=mailto:dmarc-reports@example.com; ruf=mailto:dmarc-forensic@example.com; adkim=s; aspf=s
```

Deploy DMARC in phases — jumping directly to `p=reject` without monitoring will block legitimate email.

| Phase | Policy | Action |
|:------|:-------|:-------|
| 1 | `p=none` | Monitor only; analyze reports to identify legitimate senders that fail authentication |
| 2 | (still `p=none`) | Fix SPF and DKIM for all identified legitimate senders |
| 3 | `p=quarantine` | Mark failing messages as suspicious |
| 4 | `p=reject` | Reject messages that fail both SPF and DKIM alignment |

### Null MX

Domains and subdomains that do not send or receive email must publish a null MX record (RFC 7505):

```dns
@ IN MX 0 .
```

This explicitly signals to sending servers that the domain does not accept mail, reducing backscatter and abuse.

---
[Back to Overview](./OVERVIEW.md)
