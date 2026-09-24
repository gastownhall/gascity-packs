This is the `implementation-item-base` methodology contract shared-drain item
step.

Concrete methodology packs override this step to perform one single-lane item
of implementation work with optional context from `{{context_path}}`. Do not
create parallel work inside this shared-drain contract.

Default fallback behavior must still enforce the worktree contract: resolve the
source anchor from workflow metadata, read the authoritative worktree from the
source anchor, and `cd "$WORKTREE"` before source reads, edits, tests, hashes,
or commits. `gc.work_dir` is the launcher rig root, not the implementation
worktree. When reading beads with `gc bd show --json`, handle both an object and a
one-element list before reading metadata.

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

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. Before closing this step, read the launcher rig root from the workflow root bead's `gc.work_dir`, then run the same validator locally from that rig root with `GC_BEAD_ID=<claimed-step-id> .gc/scripts/checks/build-artifact-valid.sh`; fix every reported validation error before setting `gc.outcome=pass`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
