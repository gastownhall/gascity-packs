Terminal latch for continuation convoy validation and drain.

`prepare-convoy` is the scope's abort gate. When convoy validation closes with
`gc.outcome=fail`, core skips the still-open implementation drains before they
create child workflow roots, drain controls, or worktrees, and closes this
scope with `gc.outcome=fail`. The `prepare-review` handoff sits outside the
scope, so it still runs and records the failure.
