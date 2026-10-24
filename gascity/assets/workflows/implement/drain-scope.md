Terminal latch for implement validation and drain.

`prepare` is the scope's abort gate. When validation closes with
`gc.outcome=fail`, core skips the still-open drain members before they create
child workflow roots, drain controls, or worktrees, and closes this scope with
`gc.outcome=fail`. The aggregate wait and summary steps sit outside the scope,
so they still run and record the failure.
