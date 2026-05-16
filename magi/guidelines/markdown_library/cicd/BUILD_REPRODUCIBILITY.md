# Build Reproducibility and Determinism

### Pin All Versions

Pin all build tool versions explicitly:
- Runtime versions: `Node 20.11.1`, `Python 3.12.2`, `Go 1.22.1`
- Package manager versions
- CI runner images

Version ranges (`node:20`, `python:3`) resolve to different patch versions over time, introducing non-determinism. Use exact version tags or SHA digests for container images.

### Lockfile Installs

Commit lockfiles to version control:
- `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`
- `Pipfile.lock`, `poetry.lock`
- `go.sum`
- `Cargo.lock`
- `composer.lock`

Install from lockfiles in CI:
- `npm ci`
- `pip install --require-hashes`
- `yarn --frozen-lockfile`

**Never run install commands that modify the lockfile during CI builds.**

### Pin Third-Party Actions by SHA

```yaml
# Wrong — mutable tag
uses: actions/checkout@v4

# Correct — immutable SHA
uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11
```

This prevents supply chain attacks where a compromised action tag points to malicious code.

### Artifact Metadata

Tag build artifacts with:
- Source commit SHA
- Build timestamp
- Pipeline run ID

Embed in container image labels, binary version strings, or sidecar metadata files.

### Containerized Build Isolation

Use containerized build environments (Docker, Podman, or CI-provided containers) to eliminate dependency on runner-installed tools. Each build starts from a known base image with explicitly installed dependencies. **Builds must not depend on tools or state left by previous pipeline runs on the same runner.**

---
[Back to Overview](./OVERVIEW.md)
