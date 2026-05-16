# Pipeline Performance and Cost

### Duration Targets

| Phase | Target |
|:------|:-------|
| PR feedback (lint + test + build) | < 15 minutes (ideal: < 10) |
| Beyond 30 minutes | Causes context-switching, batching, loss of flow |

Measure and optimize the **critical path** — the longest sequential chain of dependent jobs.

### Right-Size Runners

Large runners cost more per minute. Small runners take longer per job. Profile pipeline jobs to identify CPU-bound vs I/O-bound stages. Use larger runners for compilation-heavy jobs and smaller runners for linting and lightweight tests.

### Resource Cleanup

Clean up after pipeline runs:
- Delete ephemeral preview environments
- Prune untagged images from registries
- Delete expired cache entries
- Terminate orphaned cloud resources

CI-created resources without cleanup accrue costs indefinitely.

---
[Back to Overview](./OVERVIEW.md)
