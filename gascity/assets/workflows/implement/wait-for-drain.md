
Wait only on the core drain control bead and its `gc.drain_manifest.v1` rows.
Success requires the drain control to be closed with `gc.drain_state=succeeded`
and `gc.outcome=pass`, and every manifest row to have `status=succeeded` and
`outcome_kind=pass` or a selected source anchor already closed with
`gc.outcome=pass`. Failed, skipped, abandoned, or still-open manifest rows make
implement fail and write the aggregate summary.

A drain control closed with `gc.outcome=skipped` and no `gc.drain_manifest.v1`
rows was skipped because validation failed: `prepare` closed with
`gc.outcome=fail`, which aborted the `drain-scope` scope, so core skipped the
drain before it created any implementation work and closed `drain-scope` with
`gc.outcome=fail`. Treat a skipped drain, or `drain-scope` closed with
`gc.outcome=fail`, as implement failure, never as an empty successful drain.
Close this wait step with `gc.outcome=fail` and record the `prepare` failure
reason so summarize can report why no implementation ran.

Do not wait for or inspect downstream steps that depend on this bead, including
summarize, workflow-finalize, or root workflow closure; those cannot progress
until this bead closes. Do not close the input convoy head or the root workflow.
On success, close only this wait step with `gc.outcome=pass`. Summary path
override is {{summary_path}}.
