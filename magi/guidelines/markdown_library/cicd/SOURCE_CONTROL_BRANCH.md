# Source Control and Branch Strategy

### Protected Main Branch

Protect main/production with required status checks. Merges require:
- Passing CI pipeline (lint + test + build minimum)
- Code review approval
- No merge conflicts

**Direct pushes to protected branches are prohibited** for all contributors except break-glass emergency procedures with post-hoc review.

### Signed Commits

Require signed commits on protected branches where the platform supports it (GitHub, GitLab, Gitea). GPG or SSH commit signing provides non-repudiation — proof that the commit originated from the claimed author. **Unsigned commits from impersonated accounts are undetectable without signing.**

### Short-Lived Feature Branches

Use short-lived feature branches merged via pull/merge request. Branch lifetime should not exceed a few days. Long-lived branches accumulate merge conflicts, diverge from main, and delay integration feedback. Trunk-based development with feature flags is preferred for high-velocity teams.

### Semantic Version Tags

Tag releases with semantic versioning (`vMAJOR.MINOR.PATCH`):
- Tags are **immutable** — never delete and recreate a tag
- CI pipelines trigger release workflows on tag creation
- The tag references the exact commit SHA that produced the released artifact

### Automated Changelogs

Generate changelogs automatically from conventional commit messages or PR labels during the release pipeline. Manual changelogs are incomplete and inconsistent.

---
[Back to Overview](./OVERVIEW.md)
