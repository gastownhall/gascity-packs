# Access Control and Internal Governance

Session recordings reveal intimate details of user behavior: where they clicked, what they typed (even masked, interaction patterns are visible), how long they hesitated, and what errors they encountered. **Internal access to recordings must be restricted to personnel with a legitimate business need.**

### Role-Based Access

| Role | Access? |
|:-----|:--------|
| Product managers | Yes |
| UX researchers | Yes |
| Support engineers | Yes |
| Developers debugging specific issues | Yes |
| Marketing | **No** |
| Sales | **No** |
| Finance | **No** |

Apply the **principle of least privilege** to recording platform access.

### SSO/SAML and MFA

Enable SSO/SAML authentication for the recording platform. Integrate with the organization's identity provider (Azure AD/Entra ID, Okta, Auth0, Google Workspace). **Enforce MFA on recording platform access.**

### Access Logging

Log access to individual session recordings:

- Who viewed which session.
- When.
- From which IP.

This provides an audit trail for data protection impact assessments (DPIA), breach investigations, and internal compliance reviews. Most enterprise-tier recording platforms provide access logs. Self-hosted deployments must implement access logging in the application layer.

### No Raw Export

Prohibit downloading or exporting raw session recordings to local machines, shared drives, or communication channels (Slack, email). Recordings viewed in the platform's secure UI are governed by access controls and retention policies. Exported recordings bypass both. **If sharing is necessary for cross-team collaboration, share session replay URLs within the platform, not exported video files.**

---
[Back to Overview](./OVERVIEW.md)
