# Third-Party Sender Alignment

Most organizations send email through multiple services: corporate email (Google Workspace, Microsoft 365), marketing automation (Mailchimp, HubSpot, Klaviyo), transactional email (SendGrid, Postmark, SES), CRM (Salesforce, HubSpot), helpdesk (Zendesk, Freshdesk), and internal monitoring. Each service must be configured for SPF and DKIM alignment with the organizational domain.

### Sender Inventory

Maintain a documented list of every service authorized to send email using any organizational domain or subdomain. Include:

- Service name
- Sending domain(s)
- SPF mechanism (include or IP)
- DKIM selector(s)
- DKIM alignment status
- Business owner responsible for the integration

Review the inventory quarterly and when onboarding or offboarding any service.

### Custom DKIM per ESP

For every third-party ESP, configure custom DKIM signing with a key on the organizational domain. Most ESPs support this:

```dns
selector._domainkey.example.com  CNAME  selector.esp-domain.com
```

This achieves DKIM alignment because the `d=` value in the signature matches the organizational domain.

### Custom Return-Path for SPF Alignment

Where possible, configure custom Return-Path / envelope sender domains on third-party ESPs to achieve SPF alignment in addition to DKIM alignment. Custom bounce domains (`bounces.example.com`) require adding the ESP's SPF include to the subdomain's SPF record. **Dual alignment** (both SPF and DKIM) provides redundancy — if one mechanism fails for a specific message, the other satisfies DMARC.

### Onboarding and Offboarding

- **Onboarding:** Complete authentication configuration (SPF include, DKIM selector, Return-Path domain) **before** sending any production email through the service. Sending unauthenticated email from a new service after DMARC enforcement is deployed causes that email to be quarantined or rejected.
- **Offboarding:** Remove the SPF include mechanism and DKIM selector DNS records after confirming no in-flight messages remain. Removing records for active services causes immediate authentication failure. Leaving records for decommissioned services wastes SPF lookup budget and authorizes servers that may be repurposed.

---
[Back to Overview](./OVERVIEW.md)
