# Core Principles

These guidelines define strict, scalable, and maintainable patterns for identity, authorization, and secrets, optimizing for:

- **Zero Trust by Default**: Every request is unauthenticated until proven otherwise. No implicit trust based on network location, source IP, or prior request history. Internal services authenticate to each other with the same rigor as external-facing APIs. The perimeter is not the security boundary — identity is.
- **Least Privilege**: Every identity (user, service, machine) receives the minimum permissions required for its function. Broad roles (admin, superuser) are reserved for break-glass scenarios. Default permissions are zero. Access is granted explicitly, never inherited by proximity or convention.
- **Secrets Are Liabilities**: Every secret is an attack surface. Minimize the number of secrets. Minimize their lifetime. Minimize who and what can access them. Prefer short-lived, automatically-rotated credentials over long-lived static secrets. A secret that does not exist cannot be compromised.
- **Defense in Depth**: Authentication is one layer. Authorization is another. Input validation, rate limiting, anomaly detection, and audit logging are additional layers. No single mechanism is sufficient.
- **Fail Closed**: When authentication or authorization cannot be determined (IdP unavailable, token validation fails, permissions lookup errors), deny access. Never default to allow. A momentary outage of the identity provider is preferable to a momentary window of unauthenticated access.

### Primary Rule: Authentication and Authorization Are Separate Concerns

Authentication answers "who are you?" Authorization answers "what can you do?" They live in separate layers. A valid identity does not imply any specific permission. Mixing the two — for example, embedding role decisions in JWT issuance and trusting them on the consumer side without a separate authorization check — collapses the security model to whichever layer fails first.

### Secondary Rule: Every Endpoint Declares Its Auth Requirements Explicitly

Every API endpoint, server route, and protected resource declares its authentication and authorization requirements explicitly. Unauthenticated access is intentional and documented, never accidental. The default for every new endpoint is "requires authentication"; opting out is an explicit, reviewed decision.

---
[Back to Overview](./OVERVIEW.md)
