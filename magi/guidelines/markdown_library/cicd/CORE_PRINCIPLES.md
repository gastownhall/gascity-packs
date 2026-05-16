# Core Principles

These guidelines define strict, platform-agnostic conventions for CI/CD, optimizing for:

- **Pipeline Is Code**: Every pipeline definition, workflow template, reusable action, and deployment script is version-controlled, reviewed, and tested with the same rigor as application code. A pipeline that exists only in a CI platform's web UI is undocumented, unreviewable, and unreproducible. **If the CI platform disappears tomorrow, every pipeline must be reconstructable from the repository alone.**
- **Hermetic Builds**: Builds depend only on explicitly declared inputs — source code at a specific commit, pinned dependencies at exact versions, and declared build tools at known versions. Builds do not depend on ambient state on the runner. A hermetic build produces identical output given identical inputs regardless of when or where it runs.
- **Immutable Artifacts**: Once a build produces an artifact (container image, binary, package, archive), that artifact is immutable. The same artifact promotes through environments (staging → production) without rebuild. Promotion is a metadata change (tag, deployment manifest), not a new build. Artifacts are identified by content-addressable digests (SHA-256), not mutable tags.
- **Shift Left Everything**: Move validation as early as possible. Linting runs before tests. Tests run before builds. Security scanning runs before deployment. A bug caught in a pre-commit hook costs minutes; the same bug caught in production costs hours, money, and trust.
- **Zero Trust Pipeline**: The pipeline itself is an attack surface. Compromised CI runners, malicious pull requests, poisoned dependencies, and stolen secrets are all credible threats. Every step operates with minimum privilege. Secrets are scoped to the stages that need them. Third-party actions and plugins are pinned to immutable references.

### Primary Rule: Pipeline Definitions Live in the Repository

All pipeline definitions live in the repository they serve, version-controlled alongside application code. **No pipeline logic exists solely in CI platform UI configuration.**

### Secondary Rule: Every Run Is Traceable to a Commit

Every pipeline run is traceable to a specific commit SHA, triggered by a specific event (push, PR, tag, schedule, manual), and produces artifacts linked to that commit. **Traceability is non-negotiable** for audit, debugging, and incident response.

---
[Back to Overview](./OVERVIEW.md)
