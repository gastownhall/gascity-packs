# Deliverability Best Practices

Authentication is necessary but not sufficient for inbox delivery. Mailbox providers evaluate authentication alongside reputation, content, and engagement signals.

### Complaint Rate

Keep spam complaint rates below 0.1% (Google's threshold) and ideally below 0.08%. Rates above 0.3% trigger throttling and blocking regardless of authentication status. Monitor via Google Postmaster Tools and feedback loops from other providers. Implement one-click List-Unsubscribe (RFC 8058) on all marketing email to provide an alternative to the spam button.

### Stream Separation

Use separate subdomains or domains for different email streams:

| Stream | Example |
|:-------|:--------|
| Transactional | `orders@app.example.com` |
| Marketing | `news@marketing.example.com` |
| Corporate | `user@example.com` |

Reputation isolation prevents a marketing campaign's poor engagement from dragging down transactional email deliverability. Each stream has its own DKIM selector, SPF record (on the subdomain), and independent reputation.

### Forward-Confirmed Reverse DNS (FCrDNS)

Implement FCrDNS for all sending IPs. The IP's reverse DNS (PTR record) must resolve to a hostname, and that hostname must resolve forward (A/AAAA record) to the same IP. Many receiving servers check FCrDNS as a basic sender hygiene signal.

### One-Click List-Unsubscribe

Implement `List-Unsubscribe-Post` header (RFC 8058) on all bulk/marketing email. Gmail and Yahoo require one-click unsubscribe for bulk senders.

```http
List-Unsubscribe: <https://example.com/unsubscribe?id=abc>, <mailto:unsubscribe@example.com>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```

Enables inbox-level unsubscribe without opening a browser, reducing spam complaints.

---
[Back to Overview](./OVERVIEW.md)
