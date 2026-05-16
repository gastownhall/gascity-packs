# Defense in Depth

Multiple, independent layers protect API design and runtime from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Schema-first contract** — Every endpoint MUST be defined by an OpenAPI/GraphQL schema; the schema is the source of truth and is generated into types for both producer and consumer.
2. **Request and response validation** — Both incoming requests AND outgoing responses MUST be validated against the schema at runtime.
3. **Versioning strategy** — Breaking changes MUST go through a versioning policy (URI versioning or header-based) with documented sunset dates.
4. **Rate limiting and quotas** — Every public endpoint MUST be rate-limited per identity AND per source.
5. **Retries and idempotency** — Mutating endpoints MUST support idempotency keys; clients MUST retry safely.
6. **Circuit breakers** — Outbound calls MUST have circuit breakers; cascading failures MUST NOT propagate across services.
7. **Contract tests** — Consumer-driven contract tests (Pact or equivalent) MUST run in CI for every producer-consumer pair.
8. **Monitoring and SLOs** — Latency, error rate, and saturation MUST be alerted on per-endpoint SLOs.
9. **Shakedown** — §19 covers integration paths the unit and contract suites cannot.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A schema-valid request is one signal. It does NOT prove the semantics are correct.
- **Two is a tie** — Producer tests + consumer tests passing in isolation is two signals; only a contract test catches drift between them.
- **Three is a quorum** — Schema validation + contract test + production observability form the triple. All three MUST agree before promoting an API change.

Example: A producer that adds a field with a default value passes its own tests, the consumer's mocked tests pass, but a contract test catches that the consumer ignores unknown fields incorrectly — the third voter prevents production drift.

---
[Back to Overview](./OVERVIEW.md)
