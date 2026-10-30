Check whether recent successful Slack posts are receiving verified event callbacks.

Exit code is 0 when healthy, 1 when callbacks are stale, and 2 when the
durable liveness state cannot be measured.
