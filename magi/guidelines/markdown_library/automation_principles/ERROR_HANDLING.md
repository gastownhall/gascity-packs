# Error Handling and Recovery

Errors are inevitable. Self-healing automation anticipates errors, classifies them, and responds appropriately. The goal is not to prevent all errors but to handle errors gracefully when they occur.

### Error Classification

| Class | Condition | Response |
|:------|:----------|:---------|
| Transient | Temporary; may resolve without intervention | Retry with backoff |
| Recoverable | Permanent; automation can correct | Apply correction and retry |
| Fatal | Cannot resolve | Terminate with diagnostics |
| Degraded | Affects non-critical functionality | Continue with reduced capability; log clearly |

### Error Context Preservation

When errors propagate, preserve context:

- Original error message and type
- Operation being attempted
- Input values (sanitized of secrets)
- Environment state at failure time
- Sequence of operations leading to failure

"Connection refused" is insufficient. "Connection refused to database at db.internal:5432 after 3 retries during initial health check with timeout 30s" enables action.

### Cleanup on Failure

Partial execution must not leave systems in broken states:

- Delete partially created resources
- Release acquired locks
- Restore modified files from backups
- Terminate spawned processes
- Close open connections

Cleanup logic must be robust against cleanup failures. **A failed cleanup should not mask the original error.**

### Exit Codes

| Code | Meaning | Response |
|:-----|:--------|:---------|
| 0 | Success | Proceed to next step |
| 1 | General failure | Check logs for details |
| 2 | Misuse (bad arguments) | Fix invocation |
| 64-78 | Specific error categories | Handle based on category |
| 126 | Permission denied | Elevate privileges |
| 127 | Command not found | Install dependency |
| 130 | Interrupted (SIGINT) | User cancelled |
| 137 | Killed (SIGKILL) | OOM or external termination |

Define and document application-specific exit codes. **Never exit with code 0 on failure.**

---
[Back to Overview](./OVERVIEW.md)
