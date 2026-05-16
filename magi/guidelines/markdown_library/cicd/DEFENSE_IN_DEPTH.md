# Defense in Depth

Multiple, independent layers protect the CI/CD pipeline from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Static checks stage** — type-check + lint + format + security-scan MUST run before any build; failure here MUST short-circuit the pipeline.
2. **Unit and integration tests** — Unit tests MUST run in parallel; integration tests MUST run against ephemeral dependencies (test containers).
3. **Artifact immutability** — Built artifacts MUST be content-addressed and reused across stages; rebuilding per stage breaks reproducibility.
4. **Preview and staging deploy** — Every PR MUST get a preview deploy; merges to main MUST land in staging before production.
5. **Smoke tests against deployed** — Post-deploy smoke tests MUST run against the live URL/endpoint; **a green deploy step is not a green deploy.**
6. **Progressive rollout** — Production rollout MUST be canary or blue/green with automated rollback on regression.
7. **Audit trail** — Every pipeline run MUST be tied to a commit, an actor, and an immutable log; **deploys without audit are forbidden.**
8. **Pipeline shakedown** — §7 covers integration paths the build and unit suites cannot.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A green CI run is one signal. It tells you the pipeline ran, NOT that the deployed artifact works.
- **Two is a tie** — Build + tests green but staging smoke failing is the artifact-vs-runtime dissent. **The runtime wins.**
- **Three is a quorum** — Static checks + tests + post-deploy smoke against the live environment form the triple. **All three MUST agree** before promoting to production.

Example: a CI run that builds and tests on `linux/amd64` but the production host is `linux/arm64` — only the post-deploy smoke against the real architecture catches the platform mismatch.

---
[Back to Overview](./OVERVIEW.md)
