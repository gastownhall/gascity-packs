# Domain Registration and Lifecycle

### Registrar Selection

Choose a registrar based on operational requirements, not price. The cost difference between registrars is meaningless when the cheaper one lacks API access, DNSSEC support, or responsive support during an incident.

Required capabilities:

- API availability for automated management
- DNSSEC support and DS record submission
- Domain lock capabilities (registrar lock, transfer lock)
- Two-factor authentication on the registrar account
- Bulk management for portfolio operations
- Responsive support escalation path

For enterprise portfolios, GoDaddy Corporate Domains and Cloudflare Registrar both provide at-cost pricing, API access, and DNSSEC support. Cloudflare Registrar sells domains at wholesale (ICANN) pricing with no markup. GoDaddy provides dedicated account management and UDRP/URS dispute resolution services for brand protection.

### Domain Lifecycle Management

Auto-renewal must be enabled on every production domain without exception. The credit card on file must be monitored for expiration. A secondary payment method must be configured where the registrar supports it.

Domain expiry dates must be tracked in a centralized inventory **outside** the registrar dashboard — registrar dashboards are not monitoring tools. Build or adopt a domain inventory that alerts at 90, 60, and 30 days before expiration for every domain in the portfolio.

### Domain Locking

- Enable **registrar lock** (`clientTransferProhibited`) on every domain immediately after registration. This prevents unauthorized transfers.
- For high-value domains, enable **registry lock** where available — this requires manual verification through the registrar before any DNS changes, transfers, or deletions can occur. Registry lock adds friction to legitimate changes but makes domain hijacking significantly harder.

### WHOIS Privacy

Enable WHOIS/RDAP privacy on all domains unless legal or regulatory requirements mandate public registration data. Exposed WHOIS data invites:

- Social engineering attacks against domain administrators
- Phishing campaigns using registrant contact information
- Spam targeting administrative email addresses

### Defensive Registration

Register common misspellings, alternate TLDs (`.com`, `.net`, `.org`, `.io` at minimum), and hyphenated variations of primary brand domains. Redirect all defensive registrations to the primary domain with a 301. The cost of a handful of defensive registrations is trivial compared to the cost of a phishing campaign operating on a confusable domain.

---
[Back to Overview](./OVERVIEW.md)
