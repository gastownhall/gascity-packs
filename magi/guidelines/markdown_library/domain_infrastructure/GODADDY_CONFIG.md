# GoDaddy-Specific Configuration

### GoDaddy DNS Management

GoDaddy manages DNS through its web dashboard when the domain uses GoDaddy nameservers (`ns*.domaincontrol.com`). If nameservers are pointed elsewhere (e.g., Cloudflare), DNS management happens at the external provider — GoDaddy's DNS interface becomes irrelevant for record management but remains the control point for nameserver delegation, DNSSEC DS records, and domain registration settings.

GoDaddy does not support ALIAS/ANAME records at the zone apex — if you need an apex CNAME-equivalent while using GoDaddy nameservers, use an A record and manage IP changes manually, or migrate DNS to a provider that supports apex CNAME flattening.

### GoDaddy Premium DNS

Premium DNS adds:

- A secondary DNS network (Anycast)
- 100% uptime SLA
- DDoS protection on the DNS layer
- Monitoring with alert notifications

For production domains that must remain on GoDaddy nameservers, **Premium DNS is mandatory**. The standard DNS offering lacks SLA guarantees and DDoS resilience.

### GoDaddy Domain Transfers

Transferring a domain from GoDaddy to another registrar requires:

1. Unlocking the domain (disable registrar lock).
2. Obtaining the authorization/EPP code from the GoDaddy dashboard.
3. Initiating the transfer at the receiving registrar.
4. Confirming the transfer via email.

The **60-day transfer lock** applies after initial registration or a previous transfer — domains cannot be transferred within 60 days of these events. Plan migrations outside this window.

### GoDaddy as Registrar with External DNS

Recommended enterprise pattern: use GoDaddy for **domain registration** (portfolio management, brand protection, account management) while pointing nameservers to **Cloudflare** or another enterprise DNS provider. This separates registrar operations from DNS operations — each layer uses the best tool for its purpose.

Update nameservers at GoDaddy: Domain Settings → Nameservers → Change → Custom. Propagation of nameserver changes can take up to 48 hours, though most resolvers pick up changes within 1–4 hours.

---
[Back to Overview](./OVERVIEW.md)
