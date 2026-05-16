# Shakedown

### Definition

A shakedown is the first controlled, end-to-end execution of an API (or meaningfully changed API) against real downstream dependencies in a representative environment. It answers **"does the full request path actually work"** — not "is the process alive". A health check confirms the listener binds; a shakedown confirms the listener serves correct responses end-to-end.

Scope: integration validation only — not load testing, not contract testing, not user acceptance.

Environment: representative staging with real downstream services, real databases, real auth provider, sandbox payment gateways, real queue brokers.

### Shakedown vs Health Check vs Liveness vs Readiness

| Check | Question answered | Lifecycle stage |
|:------|:------------------|:----------------|
| Liveness | Is the process running and not deadlocked? | Continuous |
| Readiness | Is the process willing to accept a request right now? | Pre-traffic |
| Health | Are internal components OK (DB ping, cache ping, queue ping)? | Continuous |
| **Shakedown** | **Does the end-to-end request path produce correct responses against real dependencies?** | **Pre-promotion / startup** |

### Validation Surfaces

Shakedown exercises the actual failure surfaces of an HTTP/gRPC API. Mocked dependencies hide the faults shakedown exists to detect.

1. **Route registration** — every declared path resolves to the correct handler (no duplicate routes, no missing routes, no 404 on expected endpoints)
2. **Middleware chain** — request flows through auth, logging, tracing, rate-limiting, CORS, body parsing in declared order without being dropped
3. **Request/response serialization** — representative payloads round-trip through the serializer/deserializer without field loss, type coercion errors, or schema drift
4. **Authn/authz middleware** — valid token accepted, expired token returns 401, insufficient scope returns 403, missing token returns 401
5. **Downstream HTTP/gRPC clients** — every client connects, authenticates, and returns a deserializable response on a known-good call
6. **Persistence layer** — DB connection pool initializes, a known-good query executes, results deserialize, connection is released
7. **Pagination and filter contract integrity** — cursor advances correctly, filters apply correctly, sort order is honored, total counts match when claimed
8. **Rate-limiting and circuit-breaker primitives** — counter increments, breaker state transitions on simulated downstream failure
9. **OpenAPI schema validation** — actual responses validate against the published OpenAPI schema for every shakedown endpoint

### Mandatory Triggers

- First deployment of a new service or new API version
- Any change to route definitions, middleware chain, or request pipeline wiring
- Any change to request/response schemas or serialization configuration
- Upgrade of the HTTP framework, serialization library, ORM, or any middleware dependency
- Change of downstream service endpoints, auth provider, or database connection strings
- Infrastructure change: runtime version, base image, orchestrator, load balancer, TLS termination point
- Repair after an integration failure — the fix itself must be validated end-to-end before promotion

Forbidden:
- Skipping shakedown after "just a config change" that touches connection strings or auth configuration
- Skipping shakedown after a minor framework patch upgrade — patch releases have broken middleware ordering

### Non-Triggers

- Pure business-logic change inside an existing handler with no schema or dependency changes
- Documentation-only changes (README, OpenAPI descriptions without schema changes)
- Log-message text adjustments that do not alter log levels or fields
- Test-only changes with no production-code impact

### Execution Principles

- **Conservative inputs** — representative payloads, never edge cases, never fuzz inputs, never adversarial inputs
- **Progressive stress** — start with one request to one endpoint, then expand endpoints, then expand concurrency. Stop at the first failure.
- **Controlled environment** — staging with real downstream services isolated from production data; sandbox API keys only
- **Observable execution** — verbose request/response logging, full middleware trace, downstream call timings captured, correlation IDs preserved end-to-end
- **Known-good inputs** — a fixed corpus of requests with known expected responses per endpoint
- **No optimization** — performance issues observed during shakedown are logged and deferred; shakedown validates correctness, not latency

### Service-Side Startup Shakedown Sequence

A self-test sequence executed before the listener binds the port. The service fails to start if any step fails:

```text
Step 1: Confirm preflight — required env vars present, config schema valid, secrets resolvable from secret store
Step 2: Initialize DB connection pool — execute a known-good SELECT against a shakedown table; verify row deserializes
Step 3: Resolve downstream service endpoints — DNS lookup and TLS handshake against every declared downstream base URL
Step 4: Fetch and verify JWKS from identity provider — confirm at least one expected kid is present
Step 5: Register routes; enumerate the router and assert every declared endpoint resolved to a handler
Step 6: Execute an in-process loopback request against /shakedown that exercises the full middleware chain, hits the DB, calls one downstream service with a known-good payload, and returns a structured result envelope
Step 7: Validate the loopback response against the OpenAPI schema
Step 8: Record shakedown artifacts (timestamped log, per-step result, environment snapshot — service version, dependency versions, config hash); only then bind the listen port
```

### Release-Pipeline Shakedown Stage

A dedicated `pre-promotion-shakedown` stage that runs a small fixed suite of end-to-end API flows against the staged service with real downstream dependencies. Promotion to production is blocked until this stage passes:

- **Input**: known-good request corpus per endpoint, pinned to this release
- **Input**: staging environment wired to production-equivalent downstreams (sandbox tenant)
- **Execution**: issue each request in sequence, capture response status, body, headers, and downstream spans
- **Verification**: status matches expected, response body matches expected schema, downstream spans confirm the expected service was called
- **Artifacts**: execution log with full request/response pairs and trace IDs; result summary per endpoint; issue list with reproduction context for every anomaly; environment snapshot — service image digest, downstream versions, config values, feature-flag state

### Result Classification

- **pass** — All endpoints respond correctly, all downstream integrations verified, all schemas validate; release cleared to promote.
- **fail-blocking** — Integration fault preventing correct operation. Fix and re-run from step one. Promotion blocked.
- **fail-nonblocking** — Observed anomaly that does not prevent operation (e.g. slower than baseline) but requires a ticket with full diagnostic context.
- **inconclusive** — Environment or input limitation prevented validation of a critical path. Adjust and re-run the affected step.

### Anti-Patterns (Forbidden)

- Treating readiness or health endpoints as a substitute for shakedown — they answer different questions
- Running shakedown against mocked downstreams — the failures shakedown exists to catch hide behind mocks
- Running shakedown in an ephemeral environment whose database schema or downstream versions differ from production
- Expanding shakedown into a behavioral test suite — shakedown is a small fixed corpus, not assertion-heavy coverage
- Optimizing API code during shakedown — note it, log it, move on; optimization introduces new changes that themselves need validation
- Skipping artifact capture because "the run passed" — a shakedown without artifacts is a shakedown that never happened

---
[Back to Overview](./OVERVIEW.md)
