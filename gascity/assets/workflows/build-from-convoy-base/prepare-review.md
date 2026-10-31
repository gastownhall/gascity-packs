This is the `build-from-convoy-base` handoff into the inherited review suffix.

Read the drain result for the implementation convoy and record the
implementation evidence path as `gc.implementation.summary_path` or
`gc.build.implementation_summary_path` on the workflow root. Then validate the
inputs required by `build-from-review-base`.

A drain closed with `gc.outcome=skipped` was skipped because validation failed:
`prepare-convoy` closed with `gc.outcome=fail`, which aborted the
`drain-scope` scope before any implementation work existed, and core closed
`drain-scope` with `gc.outcome=fail`. Treat a skipped drain, or `drain-scope`
closed with `gc.outcome=fail`, as a failed continuation: close this step with
`gc.outcome=fail` and record the `prepare-convoy` failure reason instead of
handing missing implementation evidence to review.

Do not review or fix code in this step. Close only after the review suffix can
consume the implementation evidence without inspecting drain internals.
