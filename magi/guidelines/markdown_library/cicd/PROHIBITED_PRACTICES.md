# Prohibited Practices

### Never Do

- Store secrets as plaintext values in pipeline YAML, Dockerfiles, scripts, or any version-controlled file
- Reference third-party CI actions/plugins by mutable tag (`v4`, `latest`); pin by full SHA digest
- Leave the main branch unprotected; require status checks, reviews, and no direct pushes
- Bypass quality gates (tests, scans, approvals) to accelerate deployment
- Rebuild artifacts for production instead of promoting the tested artifact from staging
- Run `env`, `printenv`, or `set -x` in pipelines where secrets are present
- Share self-hosted runners between public and private repositories without trust-level isolation
- Apply infrastructure changes from developer workstations
- Deploy to production without a tested rollback procedure and retained previous artifacts
- Expose repository secrets to PR workflows from forks
- Cache credentials, tokens, `.env` files, or signing keys in CI cache layers
- Deploy artifacts to production without signature verification
- Use floating version ranges for production application dependencies without lockfiles
- Commit IaC state files (`terraform.tfstate`) to version control
- Add automatic retry logic to mask flaky tests instead of fixing them
- Skip pipeline shakedown after triggers in §7
- Run shakedown against mocked downstreams or on a different artifact than the build produced

### Always Do

- Store all pipeline definitions in the repository
- Organize pipelines into sequential stages (lint → test → build → scan → publish → deploy)
- Protect main branch with required status checks, code review, no direct pushes
- Store all secrets in CI platform secret stores or external secret managers
- Use OIDC federation for cloud provider authentication
- Pin all build tools, base images, and third-party actions to exact versions or SHA digests
- Install dependencies from lockfiles in CI
- Run dependency and container image vulnerability scanning on every PR and merge
- Sign all published artifacts with Sigstore Cosign keyless signing
- Verify artifact signatures before deployment to any environment
- Generate and publish SBOMs alongside artifacts during the build stage
- Maintain separate environments with separate secrets, configs, and deployment targets
- Require human approval for production deployments with audit trail
- Promote tested artifacts through environments without rebuilding
- Maintain rollback capability with retained previous artifacts and tested procedures
- Use ephemeral runners that reset between jobs
- Run SAST tools on every PR; block on high-severity findings
- Track pipeline duration, success rate, and DORA metrics on a visible dashboard
- Retain pipeline logs, approval records, and artifact metadata per compliance requirements
- Run pipeline shakedown after every trigger condition in §7

---
[Back to Overview](./OVERVIEW.md)
