# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Self-Healing | Detect, correct, verify before every operation; six-phase loop |
| Dependencies | Verify existence; install if missing; verify after installation |
| Environment | Detect OS, distribution, architecture, container, CI; adapt accordingly |
| Configuration | Five-source precedence; validate all values; envsubst templating with validation |
| Error Handling | Classify errors; retry transient; correct recoverable; fail fast on fatal |
| Retry | Exponential backoff with jitter; circuit breaker for repeated failures; bounded attempts |
| Health Checks | Startup wait; liveness; readiness — distinct concerns |
| Logging | Structured format; include timestamp, level, component, context; never log secrets |
| Secrets | Environment or files; never in code; never in logs; clear after use; rotate without downtime |
| Network | Verify connectivity; timeout all operations; retry with backoff |
| Files | Absolute paths; atomic writes; backup before modify; clean up temp files |
| Processes | Verify start; graceful stop; handle signals; manage PIDs |
| Idempotency | Check-then-act; atomic transitions; persist state; verify outcomes |
| Deployment | Blue-green / canary / rolling; health-gated promotion; automatic rollback on regression |
| Feature Flags | Cached check; percentage rollout via consistent hashing |
| Scheduled Tasks | Lock to prevent concurrency; jitter to prevent thundering herd; heartbeat to monitoring |
| Testing | Unit, integration, end-to-end; fresh-system validation; failure injection |
| Shakedown | Real subsystems + bounded environment + four artifacts + classified outcome |
| CI/CD | Appropriate exit codes; machine-parseable output; resource cleanup |
| Cross-Platform | Detect and adapt; POSIX where possible; platform-specific only when necessary |
| Defense in Depth | Idempotent + dry-run + validation + audit + rollback + post-check + monitoring + shakedown |

---

Following these rules produces automation that runs successfully on fresh systems, recovers from failures automatically, provides clear diagnostics when recovery fails, and operates consistently across environments. The investment in self-healing automation pays dividends every time the automation runs without requiring manual intervention — which should be every time.

**Apply these principles universally to all automation code across the organization.**

---
[Back to Overview](./OVERVIEW.md)
