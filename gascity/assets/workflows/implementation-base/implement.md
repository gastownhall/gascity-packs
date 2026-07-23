This is the `implementation-base` methodology contract implementation step.

Concrete methodology packs override this step to apply their native
implementation discipline. Work only inside the prepared worktree and preserve
the source anchor for the close step.

Core separately drained implementations obtain and verify their owner workspace
before any source read, edit, test, hash, `git add`, or `git commit`:

```sh
gc gc workspace path --step-id "<claimed-step-id>"
gc gc workspace verify-entry --step-id "<claimed-step-id>"
```

Work only in the returned workspace. Treat a missing or invalid workspace as
fatal. Never infer or reconstruct its location, and do not repair workspace
state. After a clean commit and test completion, record the exact result:

```sh
gc gc workspace record-result --step-id "<claimed-step-id>"
```

No-change results are valid. Close this step with pass only after that command
succeeds.

For artifact validation, read the launcher rig root from the workflow root bead's `gc.work_dir`, then run:

```sh
GC_BEAD_ID="$CLAIMED_STEP_ID" .gc/scripts/checks/build-artifact-valid.sh
```

fix every reported validation error before setting `gc.outcome=pass`.


Write the per-item implementation summary as a `gc.build.implementation-summary.v1`
artifact and record its absolute path on the workflow root bead as
`gc.implementation.summary_path` before closing.

The summary body must contain these exact schema-required `##` headings in this
order:

- `## Summary`
- `## Intended Behavior`
- `## Changed Files`
- `## Verification`
- `## Remaining Risks`

Artifact validation gates this step and validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. Fix every reported validation error before setting `gc.outcome=pass`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
