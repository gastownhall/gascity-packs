# Dependency Management and Supply Chain Security

### Vulnerability Scanning

Run dependency vulnerability scanning on every PR and on a schedule against main:
- `npm audit`, `pip-audit`, `cargo audit`
- Trivy, Snyk, Dependabot, Renovate

**Block merges on high/critical severity vulnerabilities** unless explicitly triaged and documented as accepted risk with a remediation timeline.

### Pin Dependencies

Pin to exact versions in lockfiles. **Do not use floating version ranges** (`^`, `~`, `>=`) for production dependencies in application code. Version ranges are acceptable in libraries (to avoid dependency hell for consumers) but not in deployable applications. Renovate or Dependabot automates version updates as PRs.

### Hash Verification

- `npm ci` with `package-lock.json`
- `pip install --require-hashes`
- Go module checksums via `go.sum`

Hash verification detects packages that have been tampered with after publication.

### SBOM Generation

Generate a Software Bill of Materials during the build stage. Use Syft, Trivy, or native generation (`npm sbom`, CycloneDX plugins). Publish alongside the artifact. SBOMs enable downstream consumers to inventory transitive dependencies and respond quickly to newly disclosed vulnerabilities.

### OpenSSF Scorecard

Evaluate the OpenSSF Scorecard for critical open-source dependencies. Scorecard assesses project health: CI tests, branch protection, dependency update tools, signed releases, vulnerability disclosure policy. **Low-scoring dependencies warrant additional scrutiny or replacement.**

### Dependency Confusion Prevention

For private package registries (npm, PyPI, NuGet, Maven), configure scope-based registry routing. Internal packages resolve from the private registry; public packages resolve from the public registry. **Namespace your internal packages to eliminate name collisions.**

---
[Back to Overview](./OVERVIEW.md)
