# Cost Management and Plan Governance

### Billing Model

Hybrid: a per-member monthly fee plus usage-based overages. **Active Git contributors count as members** on paid plans. Reviewers who do not push code are free.

Usage dimensions:

- Build minutes.
- Bandwidth.
- Serverless function invocations.
- Edge function invocations.
- Blob storage.

### Usage Monitoring

Track these metrics against plan limits monthly:

- Build minutes consumed per month.
- Bandwidth transferred per month.
- Serverless function invocations and execution duration.
- Edge function invocations.
- Blob storage volume.

**Free plan:** exceeding limits pauses the site until next billing cycle. **Paid plans:** overages billed at published rates. Neither is acceptable for production workloads — monitor proactively.

### Cost Optimization

Reduce costs through platform-native mechanisms before introducing external tooling.

| Dimension | Optimization |
|:----------|:-------------|
| Build minutes | `ignore` command to skip unchanged builds; cache dependencies effectively; avoid rebuilds from documentation-only changes |
| Bandwidth | Image CDN for smaller images; appropriate cache headers (cache hits don't count against bandwidth); `immutable` directive for hashed static assets |
| Function invocations | Cache function responses at the CDN edge; batch API calls; use edge functions for lightweight ops that would otherwise invoke a full serverless function |

### Enterprise Controls

Enterprise plans add: SSO/SCIM integration, audit logs, SOC 2 compliance, private Git integration (GitHub Enterprise, self-managed GitLab, Bitbucket), org-level role management, deploy retention policies, 99.99% uptime SLA, and dedicated support with contractual SLAs. For regulated industries (fintech, healthcare), these controls are prerequisites, not upgrades.

---
[Back to Overview](./OVERVIEW.md)
