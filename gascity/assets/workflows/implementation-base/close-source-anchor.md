This is the `implementation-base` methodology contract source-anchor close
step.

Concrete methodology packs override this step only when they need additional
artifact checks. Core separately drained implementations obtain the recorded
current-item result for this claimed step with:

```sh
gc gc workspace result --step-id "<claimed-step-id>"
```

Use only its exact source anchor, prepared workspace, input revision, and output
revision for existing implementation-result and summary checks. Never infer or
reconstruct those values. Write the per-item summary to `{{summary_path}}` when
set. Otherwise first use `gc.implementation.summary_path` from the preceding
implementation step when present, then fall back to
`{{artifact_root}}/task-<source-anchor-id>-summary.md`.

Close only the recorded source anchor with `gc.outcome=pass`, including the
exact output revision and summary path in the close reason. Read that source
anchor back and verify `status=closed` and `gc.outcome=pass`, then call
`gc gc workspace cleanup-if-complete --step-id "<claimed-step-id>"`. Retained,
removed, and already-removed are successful outcomes; command failure is hard
and prevents this workflow step from closing with pass. Do not close a
drain-unit convoy, parent convoy, or broader workflow root.
