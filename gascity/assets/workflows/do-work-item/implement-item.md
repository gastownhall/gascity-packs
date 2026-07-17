
Run inside an existing shared worktree lifecycle. Resolve reserved `convoy_id`,
read `gc.drain_member_id` and `gc.drain_item_index`, validate ownership and
verification policy, validate context path {{context_path}} when set, implement
the item, write an item summary, and close only the source anchor on success.

Do not infer the source anchor from dependency ids. Read the reserved convoy and
source anchor metadata directly; when `gc bd show --json` returns a one-element
list, unwrap the first element before reading metadata. `gc.work_dir` is the
launcher rig root, not the implementation location. Use the authoritative
worktree recorded on the source anchor, run `cd "$WORKTREE"`, and verify
`pwd -P` equals `$WORKTREE` before any source read, source edit, test, file
hash, `git add`, or `git commit`.

Write or update the item summary with these schema-required body sections,
using the exact `##` headings below in this order:

- `## Summary`
- `## Intended Behavior`
- `## Changed Files`
- `## Verification`
- `## Remaining Risks`

The `## Verification` section must include both the first verification command
and the final proof command, with the observed pass/fail result.

Run Python proof commands with `PYTHONDONTWRITEBYTECODE=1`. Before recording
success, remove only
workflow-generated `__pycache__`, `.pyc`, and `.pyo` files; leave no generated
code/cache artifacts and never delete pre-existing user files to satisfy a gate.

Write the summary as a `gc.build.implementation-summary.v1` artifact and record
its absolute path on the workflow root bead as `gc.implementation.summary_path`
before closing. If no path is recorded, use
`<WORKTREE>/implementation-summary-<source-anchor-id>.md`; every shared-session
member needs a distinct deterministic path. If a path exists, require it to be
inside the authoritative worktree and distinct from every other member summary.
Include a Markdown coverage table. The validator only recognizes a table with
an `ID` column and a `Status` column. Use this shape:

| ID | Status |
| --- | --- |
| REQ-001 | covered |

Use mapping objects for front matter; do not use scalar shortcuts such as
`workflow: build-basic`. The top-level YAML shape must be:

- `schema: gc.build.implementation-summary.v1`
- `workflow: {id: <workflow-root-id>, formula: <root-workflow-formula>}`
- `methodology: {pack: gascity, name: build-basic}`
- `producer: {formula: do-work-item, stage: implement-item, attempt: <positive integer>}`
- Use `status: approved` before closing; a successful implementation proof must
  be approved.
- `trace: {upstream: [...], coverage: [...]}`

Trace front matter must use the validator shape exactly:

- `trace.upstream[]` entries must include `path` and `hash`; do not use
  `id`/`title`/`type` entries as the upstream shape.
- For the source anchor bead, use `path: beads/<source-anchor-id>` and
  `hash: bead:<source-anchor-id>`. For changed files or upstream build
  artifacts, use repo-relative paths and scheme-qualified hashes such as
  `sha256:<digest>` or `git:<revision>`.
- If an upstream entry lists `ids`, every listed id must appear exactly once in
  `trace.coverage` and in the Markdown coverage table with the same status.
- Coverage statuses are not artifact statuses. Use `covered` for satisfied
  requirements; do not use `approved` in `trace.coverage[].status` or the
  Markdown coverage table.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. Before closing this step, read the launcher rig root from the workflow root bead's `gc.work_dir`, then run the same validator locally from that rig root with `GC_BEAD_ID=<claimed-step-id> .gc/scripts/checks/build-artifact-valid.sh`; fix every reported validation error before setting `gc.outcome=pass`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.

After the focused product commit and final proof pass, read the full commit from
`WORKTREE` with `git rev-parse HEAD`. Persist the proof tuple on the source anchor bead itself in one update:

```bash
gc bd update <source-anchor-id> \
  --set-metadata "gc.implementation.worktree_path=$WORKTREE" \
  --set-metadata "gc.implementation.commit=<full-HEAD-from-WORKTREE>" \
  --set-metadata "gc.implementation.summary_path=<absolute-summary-inside-WORKTREE>"
```

Read the source anchor bead back. Require `work_dir` and
`gc.implementation.worktree_path` to resolve to the same worktree, the recorded
commit to equal that worktree's `HEAD`, and the recorded summary to exist
inside that worktree. Do not close the source anchor or this implementation
step with pass until the exact tuple has been read back successfully.
