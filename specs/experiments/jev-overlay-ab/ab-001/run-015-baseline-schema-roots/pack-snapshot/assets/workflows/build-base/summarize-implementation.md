Write the canonical build implementation summary.

This build-base stage may be inherited by concrete build methodology packs.
Concrete build methodology packs may override this stage, but any override must
preserve the root implementation-summary artifact contract.

The implementation drain may write one or more per-item summaries from source
worktrees. This stage converts that implementation evidence into the root
workflow artifact recorded as `gc.build.implementation_summary_path`, normally
`implementation-summary.md` under the build artifact root.

Resolve the workflow root bead and artifact root from root metadata. If
`gc.build.implementation_summary_path` is empty, derive an absolute path under
`gc.var.artifact_root` or `gc.build.artifact_root` as
`implementation-summary.md`, then record it on the workflow root:

`gc bd update "<workflow-root-id>" --set-metadata "gc.build.implementation_summary_path=<absolute path>"`

Do not use `gc bd update --metadata 'key=value'`; `--metadata` only accepts a JSON
object.

Collect the closed implementation source anchors and drain child workflows from
the implementation convoy. Read their recorded implementation summary paths
from `gc.implementation.summary_path`, `gc.build.implementation_summary_path`,
or `gc.var.summary_path`. Include those summaries as upstream evidence. If an
item summary is missing coverage IDs that appear in the requirements artifact,
read the requirements, decomposition, review context, and verification evidence
before writing the canonical root summary. The canonical summary must cover all
accepted requirement IDs that the build finalized.

Write the artifact as Markdown with YAML front matter, not JSON. Use mapping objects for front matter; do not use scalar shortcuts such as
`workflow: build-basic`. The top-level YAML shape must be:

- `schema: gc.build.implementation-summary.v1`
- `workflow: {id: <workflow-root-id>, formula: <root-workflow-formula>}`
- `methodology: {pack: <pack-name>, name: <build-formula>}`
- `producer: {formula: <build-formula>, stage: summarize-implementation, attempt: <positive integer>}`
- `status: approved` or another schema-allowed status
- `trace: {upstream: [...], coverage: [...]}`

Trace front matter must use the validator shape exactly:

- `trace.upstream[]` entries must include `path` and `hash`; do not use
  `id`/`title`/`type` entries as the upstream shape.
- For upstream build artifacts or implementation summaries, use their recorded
  paths and scheme-qualified hashes such as `sha256:<digest>`. For convoy or
  bead inputs, use `path: beads/<bead-id>` and `hash: bead:<bead-id>`.
- If an upstream entry lists `ids`, every listed id must appear exactly once in
  `trace.coverage` and in the Markdown coverage table with the same status.
- Coverage statuses are not artifact statuses. Use `covered` for satisfied
  requirements; do not use `approved` in `trace.coverage[].status` or the
  Markdown coverage table.

Include a Markdown coverage table whose ID/status pairs exactly match
`trace.coverage`. The validator only recognizes a Markdown table with an `ID`
column and a `Status` column. Use this shape:

| ID | Status |
| --- | --- |
| REQ-001 | covered |

The body must include these schema-required sections:

- Summary
- Intended Behavior
- Changed Files
- Verification
- Remaining Risks

In those sections, include the implementation convoy id, source anchor ids,
per-item summary paths, changed files, first verification commands, final proof
commands, observed pass/fail results, and remaining risks. Keep the root
summary concise, but do not omit accepted requirement IDs.

Before closing this step, read the launcher rig root from the workflow root bead's `gc.work_dir`, then run the same validator locally from that launcher rig root:

`GC_BEAD_ID=<claimed-step-id> .gc/scripts/checks/build-artifact-valid.sh`

fix every reported validation error before setting `gc.outcome=pass`. Then set
the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, and close
with `gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.implementation_summary_path` against schema `gc.build.implementation-summary.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
