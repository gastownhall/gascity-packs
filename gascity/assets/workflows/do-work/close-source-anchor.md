
Obtain the recorded current-item implementation result for this claimed step:

```sh
gc gc workspace result --step-id "<claimed-step-id>"
```

Use only its exact source anchor, prepared workspace, input revision, and output
revision for implementation-commit and summary evidence checks; do not infer or
reconstruct any of them.

Write the per-item summary to {{summary_path}} when set. If `summary_path` is
not set, first use `gc.implementation.summary_path` from the preceding
implementation step when present; otherwise use
`{{artifact_root}}/task-<source-anchor-id>-summary.md`.

On success, close only the recorded source anchor with `gc.outcome=pass`.
Include the verified exact output revision and summary path in the source-anchor
close reason. Read the source anchor back with
`gc bd show <source-anchor-id> --json` and verify `status=closed` and
`gc.outcome=pass`; if either check fails, fix the source anchor before invoking
conditional cleanup:

```sh
gc gc workspace cleanup-if-complete --step-id "<claimed-step-id>"
```

Treat `cleanup=retained`, `cleanup=removed`, and `cleanup=already-removed` as
successful outcomes. Any command failure is hard; do not close this step with
pass after a failure. Then close this step. Do not close the drain-unit convoy,
parent convoy, or broader workflow root from this step.
