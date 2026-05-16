# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Core | Pipeline is code; hermetic builds; immutable artifacts; shift left; zero trust pipeline; every run traceable to commit SHA |
| Workflow | Staged gates (lint→test→build→scan→publish→deploy); parallel independent jobs; reusable templates; explicit triggers; path filtering; timeouts on every job |
| Source Control | Protected main branch; signed commits; short-lived feature branches; semantic version tags; automated changelogs |
| Environments | Dev/staging/prod minimum; separate secrets per env; branch-to-environment mapping enforced in pipeline; ephemeral preview environments; staging mirrors production |
| Secrets | Never in YAML or VCS; masked in logs; scoped to minimum stage; OIDC over static credentials; no secrets to fork PRs; rotated on schedule; access audited |
| Builds | Pin all tool versions; lockfile installs; third-party actions by SHA digest; containerized build isolation; artifacts tagged with commit SHA and run ID |
| Shakedown | Stage between build and full-test; throwaway environment; real downstreams; happy path only; six required assertions; classified outcome; ≤ 10 min |
| Testing | Unit on every commit; integration on merge; E2E on staging; machine-parseable results; flaky test tracking and quarantine; coverage floors not maximization |
| Static Analysis | Linters and formatters on every PR; SAST on every PR; type checking as gate; IaC security scanning; block on high-severity findings |
| Supply Chain | Dependency vuln scanning; pinned versions with lockfiles; hash verification; SBOM generation; OpenSSF Scorecard evaluation; dependency confusion prevention |
| Containers | Minimal base images; scan before publish; pin by digest; no secrets in layers; multi-stage builds; non-root user; OCI annotation labels |
| Artifact Signing | Sigstore Cosign keyless signing; sign by digest; verify before deploy; SLSA provenance attestations; SBOM attestations; target SLSA Level 2+ |
| Deployment | All gates pass before production; human approval required; progressive strategies (canary/blue-green/rolling); smoke tests post-deploy; deployment windows; promote not rebuild |
| Rollback | Previous artifacts retained; rollback tested regularly; forward-compatible migrations; automated rollback triggers on metric degradation |
| Runner Security | Ephemeral runners; trust-level isolation; containerized execution; updated agent software; resource usage monitoring |
| Caching | Lockfile-keyed dependency caches; Docker layer caching; no secrets in cache; TTLs and size limits; hit rate monitoring |
| IaC | Plan on every PR; apply only from pipeline; remote state with locking; drift detection on schedule |
| Monitoring | Pipeline duration and success dashboards; main branch failure alerts; DORA metrics tracking; post-deployment metric observation gates |
| Compliance | Retained logs per framework; separation of duties; end-to-end deployment traceability; CODEOWNERS on pipeline config |
| Defense in Depth | Static checks + tests + immutable artifacts + preview/staging + post-deploy smoke + progressive rollout + audit + shakedown |

---

Following these guidelines produces CI/CD pipelines that are reproducible, secure, auditable, and resilient. Builds are hermetic; artifacts are immutable and signed; secrets stay out of source control; deployments are gated and reversible; integration faults surface in shakedown rather than in production. The pipeline is the security control — make it strong.

**Apply this guidance universally to all CI/CD pipelines across the organization, regardless of platform.**

---
[Back to Overview](./OVERVIEW.md)
