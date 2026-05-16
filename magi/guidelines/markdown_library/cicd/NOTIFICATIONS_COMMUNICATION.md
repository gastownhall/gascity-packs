# Notifications and Communication

### Notify on Failure and Recovery

**Not on every success.** Constant success notifications create noise that trains teams to ignore them.
- Notify when a pipeline fails
- Notify when a previously-failed pipeline recovers
- Notify on production deployment completion (success or failure)

### Actionable Context

Include:
- Failed stage
- Failing test names or error summary
- Commit author
- Link to the pipeline run

Wrong: `Pipeline failed`. Right: `Build stage failed: TypeScript compilation error in src/auth/handler.ts — @author — Run #4521`.

---
[Back to Overview](./OVERVIEW.md)
