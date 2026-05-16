# Authentication, Authorization, and Secrets Management Library

This directory contains an expanded, modularized version of the Authentication, Authorization, and Secrets Management Guidelines. Mandatory for all applications, APIs, server-side services, CLI tools, CI/CD pipelines, and infrastructure automation that authenticate users, services, or systems — regardless of whether the identity provider is Auth0, Azure AD/Entra ID, AWS IAM, GCP IAM, or a custom implementation. Targets OAuth 2.1 draft compliance, OpenID Connect Core 1.0, JWT (RFC 7519), JWK (RFC 7517), and PKCE (RFC 7636). Deviation is a security defect.

## Critical Mandates (Read First)
- **Authentication and Authorization Are Separate Concerns** — answers to different questions, in different layers.
- **Every Endpoint Declares Its Auth Requirements Explicitly** — default is "requires authentication"; opting out is reviewed.
- **Fail Closed** — when auth cannot be determined, deny access.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Zero trust, least privilege, secrets are liabilities, defense in depth, fail closed.
2. [Secrets Management](./SECRETS_MANAGEMENT.md) — Storage, rotation, isolation, dual-secret, audit, managed identities, encryption, scanning.
3. [OAuth 2.0 and OpenID Connect](./OAUTH_OIDC.md) — Flow selection, client types, PKCE, state, callback security, scopes.
4. [JWT Validation](./JWT_VALIDATION.md) — Mandatory steps, algorithms, JWKS caching, claim hygiene.
5. [Token Lifecycle Management](./TOKEN_LIFECYCLE.md) — Lifetimes, refresh rotation, transmission, storage, revocation, refresh patterns.
6. [Session Management](./SESSION_MANAGEMENT.md) — ID generation, cookie attributes, timeouts, logout, invalidation, storage.
7. [Auth0 Configuration Patterns](./AUTH0_PATTERNS.md) — Tenants, Actions, lifetimes, Organizations, configuration, ID token validation.
8. [Role-Based Access Control](./RBAC.md) — Permissions vs roles, granularity, delivery, ABAC, audit, API-level enforcement.
9. [Multi-Factor Authentication](./MFA.md) — Admin requirement, factor preference, step-up, recovery.
10. [CSRF Protection](./CSRF.md) — Defense mechanisms, SameSite, Origin/Referer.
11. [Password Policy and Credential Storage](./PASSWORD_POLICY.md) — Hashing, salting, NIST policy, hygiene.
12. [Cloud Platform Authentication](./CLOUD_PLATFORM_AUTH.md) — Azure/Entra ID, AWS IAM, GCP IAM, cross-cloud and hybrid.
13. [API Authentication Patterns](./API_AUTH_PATTERNS.md) — API keys, service-to-service.
14. [Audit Logging and Monitoring](./AUDIT_LOGGING.md) — Required events, anomaly alerting, log integrity.
15. [Shakedown](./SHAKEDOWN.md) — Definition, triggers, validation categories, execution, classification, anti-patterns.
16. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
17. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do / Always Do lists.
18. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
