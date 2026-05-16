# TLS-RPT (TLS Reporting)

TLS-RPT (RFC 8460) provides reports from sending servers about TLS connection successes and failures when delivering to your domain. It is the monitoring counterpart to MTA-STS and DANE — without TLS-RPT, you have no visibility into TLS delivery problems.

### Record

Publish at `_smtp._tls.example.com`:

```dns
v=TLSRPTv1; rua=mailto:tls-reports@example.com
```

This instructs sending servers to send daily JSON reports about TLS connection results. Reports include:

- Successful connections
- Negotiation failures
- Certificate errors
- Policy mode (testing vs. enforce)

### Reporting Address

Use a dedicated reporting address for TLS-RPT, separate from DMARC aggregate report addresses. TLS-RPT and DMARC reports serve different purposes and should be processed independently. Consider HTTPS reporting endpoints (`rua=https://...`) for integration with monitoring dashboards.

### Sequence with MTA-STS

Deploy TLS-RPT **before** deploying MTA-STS in enforce mode. TLS-RPT reports during MTA-STS testing mode reveal which senders have TLS issues. Fix those issues (usually certificate hostname mismatches or outdated TLS versions) before enforcement. Without TLS-RPT, MTA-STS enforcement is blind.

---
[Back to Overview](./OVERVIEW.md)
