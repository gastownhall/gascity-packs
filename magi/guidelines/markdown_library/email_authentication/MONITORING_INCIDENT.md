# Monitoring and Incident Response

Ongoing monitoring detects authentication failures, spoofing campaigns, and configuration drift before they impact deliverability or brand reputation.

### Automated Aggregate Report Processing

Process DMARC aggregate reports automatically using a DMARC analytics platform. Manual XML parsing is not sustainable beyond a single domain. The platform must:

- Visualize authentication pass/fail rates over time.
- Identify unauthorized sending sources.
- Track alignment status per ESP.
- Alert on anomalies.

### Reputation Monitoring

Monitor sender reputation:

- **Google Postmaster Tools** for Gmail delivery.
- **Microsoft SNDS** for Outlook delivery.
- Domain/IP blocklist services (MXToolbox monitoring, Spamhaus).

Authentication pass rates do not guarantee inbox delivery — reputation, content, and engagement signals also factor. But authentication failures guarantee delivery problems.

### Alerting

- **Pass rate drops** — Establish a baseline (target 98%+ for legitimate senders). Alert when the rate drops below 95%. Common causes: DKIM key expiry, ESP configuration change, SPF record modification removing a legitimate include, new sending source deployed without authentication.
- **Spoofing spikes** — A sudden increase in DMARC failures from IPs not in your sender inventory indicates an active spoofing campaign. Correlate with abuse reports and phishing complaints. Consider takedown requests against the spoofing infrastructure.

### Incident Runbook

Maintain a runbook for email authentication incidents:

- **DKIM key compromise** — rotate immediately, publish new key, monitor pass rates.
- **SPF record exceeding lookup limit** — flatten or remove unused includes.
- **DMARC policy causing legitimate mail rejection** — temporarily reduce enforcement via `pct` or `sp` tags while diagnosing.
- **Certificate expiry affecting MTA-STS or BIMI** — renew immediately, verify endpoint.

---
[Back to Overview](./OVERVIEW.md)
