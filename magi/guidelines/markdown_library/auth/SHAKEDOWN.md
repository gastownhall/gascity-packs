# Shakedown

### Definition

An authentication shakedown is the first controlled, end-to-end execution of every authentication and authorization flow against the **real identity provider, real token signing key material, real session store, and real MFA verifier**. It is **not** a unit test against a mocked IdP.

Auth integration faults — subtle clock skew with JWKS, redirect-URI mismatches, scope drift, cookie domain errors, session-store serialization bugs, refresh-rotation race conditions — hide behind mocks almost universally. Shakedown is the point at which those faults surface before real users encounter them.

### Shakedown Does Not Tolerate Mocked Identity

Mocked IdPs, stubbed JWKS, in-memory session stores, and fake TOTP generators **defeat the purpose of a shakedown**. Every shakedown run targets:
- The real Auth0 / Okta / Entra ID **sandbox** tenant
- The real JWKS endpoint
- The real Redis or database session store
- A real TOTP or WebAuthn verifier

If an integration cannot be exercised against the real dependency, it is not ready for shakedown.

### Shakedown vs Preflight vs Testing

- **Preflight** confirms static prerequisites — `client_id` present, signing cert loaded, JWKS URL reachable.
- **Shakedown** confirms the integrated auth flow produces correct outcomes under real conditions — code flow round-trips, token verifies, session persists, MFA challenge completes.
- **Testing** confirms behavioral and performance correctness — thousands of assertions, adversarial inputs, concurrency stress.

A passed shakedown is necessary before functional testing; a failed shakedown blocks every downstream phase.

### Mandatory Triggers

- First deployment of a new service
- Every IdP configuration change
- Every signing key rotation
- Every callback URL change
- Every session store replacement or upgrade
- Every JWT library upgrade
- Every MFA verifier change
- Every repair following an authentication incident

**Skipping shakedown after "small" auth configuration changes is the single most common source of production auth outages.**

### Non-Triggers

Shakedown is not required for:
- Pure business-logic changes inside an already-authenticated handler
- Content or template updates
- Documentation changes
- Test-only changes
- Changes to unrelated subsystems

### Validation Categories

Each maps to a real failure surface that has caused production outages:

1. **OIDC code-flow round-trip** — Generate `code_verifier`, build authorization URL with `code_challenge`, complete sandbox authentication, receive auth code on registered redirect URI, exchange for access + ID tokens, verify `state` matches, confirm ID token validates against real JWKS.
2. **Token signing and verification** — Resolve `kid` from token header, fetch matching public key from JWKS, verify signature, validate `iss`/`aud`/`exp`/`iat`/`nbf`. **Rotate through a key-rollover scenario** where JWKS returns both old and new keys.
3. **Refresh-token rotation under contention** — Refresh, confirm old token invalidated, replay old token, confirm reuse-detection revokes the session family. Concurrent refresh attempts must not produce duplicate valid tokens.
4. **Session store** — Create session with known payload, read from a different application instance, expire, confirm gone, confirm revocation propagates across instances. Session-store serialization bugs are invisible to unit tests and catastrophic in production.
5. **MFA challenge-response** — Enroll test authenticator, generate valid TOTP code, submit, confirm acceptance; submit expired code, confirm rejection. For WebAuthn, exercise full registration + authentication ceremony with a real authenticator. Step-up flows must also be shaken down.
6. **Logout and session invalidation propagation** — Sign in on two clients, logout on one, confirm the other is unauthenticated on next protected request. Exercise back-channel logout endpoint if RP-initiated or back-channel logout is configured.
7. **Authorization enforcement** — User with expected permission gets the resource; user without gets 403; unauthenticated request gets 401. Cover RBAC and ABAC paths.
8. **CSRF and cookie attributes** — Verify session cookies carry `HttpOnly`, `Secure`, `SameSite`, correct `Domain`/`Path` at runtime. Exercise CSRF protection: state-changing request without token rejected; with valid token succeeds.

### Execution Principles

- **Progressive execution** — simplest happy-path first (one code-flow round-trip, one user), then add complexity (refresh rotation, MFA, concurrent sessions, logout propagation). Stop at the first failure and diagnose before advancing.
- **Known-good inputs** — fixed set of test users in the sandbox tenant with known roles/permissions; known-good TOTP secret enrolled on a controlled authenticator; known-good WebAuthn credential. Shakedown is not fuzzing.
- **Full observation** — capture every HTTP request/response with correlation IDs, JWKS fetches, session store operations, MFA verifier calls. **No optimization during shakedown** — latency observations are logged and deferred.

### Reference Sequence

```text
Step 1:  Preflight: confirm client_id, client_secret (from Vault), issuer,
         JWKS URL, redirect URI present and sandbox tenant reachable
Step 2:  Generate code_verifier and code_challenge; build authorization URL
         with state, nonce, PKCE parameters
Step 3:  Drive headless browser through sandbox user authentication; capture
         redirect to registered callback URL
Step 4:  Validate returned state matches original and has not been reused;
         delete state from session
Step 5:  Exchange authorization code for access + refresh + ID tokens via
         token endpoint; confirm 200 with all expected fields
Step 6:  Verify ID token signature against real JWKS using kid from header;
         validate iss, aud, exp, iat, nbf, nonce
Step 7:  Write session into real session store; read back from a second app
         instance; confirm content matches
Step 8:  Invoke a protected API endpoint with the access token; confirm 200
         with expected payload
Step 9:  Trigger refresh-token rotation; confirm old refresh token
         invalidated; replay old token; confirm session family revoked
Step 10: Enroll shakedown test user in TOTP; complete a valid challenge;
         submit an expired code; confirm rejection
Step 11: Invoke logout; confirm session gone from store; subsequent protected
         request returns 401
Step 12: Record execution log, per-step result, issue list, environment
         snapshot (IdP tenant, service version, JWKS kid set, session store
         type and version); classify as pass / fail-blocking /
         fail-nonblocking / inconclusive
```

### Required Artifacts

- **Execution log** with every HTTP exchange and correlation ID
- **Result summary** with per-category pass/fail classification
- **Issue list** with reproduction context for every anomaly (including deferred non-blocking issues)
- **Environment snapshot** capturing sandbox tenant, IdP configuration hash, JWKS key IDs seen, service version, session store type/version

A shakedown without these artifacts is not a shakedown.

### Result Classification

- **pass** — promote
- **fail-blocking** — do not promote; fix and re-run from step one
- **fail-nonblocking** — promote only after ticket creation with full diagnostic context
- **inconclusive** — adjust environment and re-run the affected step

Silent success is prohibited.

### Anti-Patterns (Forbidden)

- Running against a mocked IdP
- Running against an in-memory session store
- Using unit-test fixtures instead of real sandbox users
- Skipping shakedown after "just a config change" to callback URLs or issuer settings
- Optimizing auth code paths during the shakedown
- Failing to capture artifacts

Any of these is cause to re-run the shakedown against a properly representative environment.

---
[Back to Overview](./OVERVIEW.md)
