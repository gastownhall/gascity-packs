Finalize the `build-basic` workflow.

Summarize requirements, implementation-plan, design-review, create-beads,
implementation, and review artifacts. Record the final outcome, artifact paths,
and remaining follow-up beads on the workflow root bead.

Before reading or writing build artifacts, inspect every direct dependency
control. Require each dependency control to be closed with `gc.outcome=pass`.
If any dependency failed or lacks that exact outcome, do not write a final
report or attempt infrastructure repair. Record `gc.build.status=failed`,
`gc.failure_class=upstream_validation`, and a concise `gc.blocked_reason` on the
workflow root; set the claimed step to `gc.outcome=fail`, close it, and stop.

Read the validated review artifact before finalizing. In report mode,
`status: changes_required` is successful review delivery but not implementation
approval. Write the configured final artifact using the schema and trace shape
below with `status: blocked`, record both final-report paths, and run the
installed artifact check. After it passes, atomically record these failure-only
values on the workflow root: `gc.outcome=fail`, `gc.build.status=blocked`,
`gc.build.finalize_status=failed`, `gc.build.finalize_outcome=failure`,
`gc.build.repair_status=repairable`,
`gc.restart.entrypoint=build-from-review`,
`gc.restart.reason=review_changes_required`,
`gc.restart.review_report_path=<canonical review report path>`,
`gc.blocked_reason=code_review_changes_required`, and
`gc.failure_class=review_iteration_needed`. Set the claimed finalize step to
`gc.outcome=fail`, close it, and stop without running the success update below.
Any other non-approved review status is invalid for this expansion; fail with a
precise blocked reason and never invent approval. A validated review with
remaining findings must never become a completed build.

Treat installed validation code as immutable infrastructure. Never create,
reconstruct, or modify `.gc/scripts`. If an installed validator or helper is
missing, record `gc.failure_class=validation_infrastructure`, close with
`gc.outcome=fail`, and stop; never author a substitute validator.

The build-basic implementation result may live in a source anchor/worktree. A
launcher rig root that still contains the original fixture is not a partial build
when the canonical implementation summary and review artifact show the source
anchor/worktree passed. Use `status: approved` for the final report in that
case, and record publish/no-op details separately.

Write the final report, normally `factory-run.md`, at the path recorded on the
workflow root bead as `gc.build.final_report_path`. The artifact must be Markdown with YAML front
matter, not JSON. Its front matter must declare
`schema: gc.build.final-report.v1`, the workflow id/formula, the methodology
pack/name, the producer formula/stage/attempt, `status`, and `trace` with
upstream and coverage entries. Include a Markdown coverage table whose
ID/status pairs exactly match `trace.coverage`.
The validator only recognizes a Markdown table with an `ID` column and a
`Status` column. Use this shape:

| ID | Status |
| --- | --- |
| REQ-001 | covered |

Before writing `factory-run.md`, ensure the canonical implementation summary
exists at the path recorded on the workflow root bead as
`gc.build.implementation_summary_path`, normally `implementation-summary.md`.
It must already be an approved `gc.build.implementation-summary.v1` artifact
whose current bytes match the selected review trace. Treat the canonical summary
and validated review as immutable inputs. If either is missing, invalid, or
mismatched, fail this stage and record a healable restart at review. Never
synthesize, mutate, replace, or repoint either artifact during finalization.

The existing canonical summary has these sections:

- Summary
- Intended Behavior
- Changed Files
- Verification
- Remaining Risks

Use mapping objects for front matter; do not use scalar shortcuts such as
`workflow: build-basic`. The top-level YAML shape must be:

- `schema: gc.build.final-report.v1`
- `workflow: {id: <workflow-root-id>, formula: build-basic}`
- `methodology: {pack: gascity, name: build-basic}`
- `producer: {formula: build-basic, stage: finalize, attempt: <positive integer>}`
- Set `producer.attempt` to the current `gc.attempt` on every write or repair.
- `status: approved` for successful finalization; use `status: blocked` only for
  the failure branch above
- `implementation_snapshot: <exact review snapshot>`
- `review_input_snapshot: <exact review-input snapshot>`
- `reviewed_attempt: <exact positive reviewed attempt>`
- `trace: {upstream: [...], coverage: [...]}`

Trace the exact canonical implementation summary once at its absolute path with
a freshly computed `sha256:<digest>`. Trace the validated review artifact once
at its absolute path with its own freshly computed digest. The extra
`implementation_snapshot: <exact review snapshot>` must equal the root and
review artifact snapshots; repeat it in Artifacts.
The review-input snapshot and reviewed attempt must exactly equal the validated
review artifact and the still-closed lane/synthesis/selected-terminal group.
Recompute the live combined value from the immutable summary and review context
before writing the final report. The review must still trace that context
exactly once; finalization verifies it transitively and never repoints it.

Trace front matter must use the validator shape exactly:

- `trace.upstream[]` entries must include `path` and `hash`; do not use
  `id`/`title`/`type` entries as the upstream shape.
- For upstream build artifacts, use their recorded paths and scheme-qualified
  hashes such as `sha256:<digest>` or `git:<revision>`. For convoy or bead
  inputs, use `path: beads/<bead-id>` and `hash: bead:<bead-id>`.
- If an upstream entry lists `ids`, every listed id must appear exactly once in
  `trace.coverage` and in the Markdown coverage table with the same status.
- Coverage statuses are not artifact statuses. Use `covered` for satisfied
  requirements; do not use `approved` in `trace.coverage[].status` or the
  Markdown coverage table.
- Do not create any additional Markdown table with both an `ID` column and a
  `Status` column unless it repeats the exact same coverage ID/status pairs.
  For requirement or artifact summaries, use different column names such as
  `Requirement` and `Result`, or use `covered` as the status for every covered
  requirement.

Keep it short and useful for a first-time factory user. Include the required
schema sections:

- Summary
- Outcome
- Artifacts
- Remaining Risks

In those sections, include:

- methodology: build-basic starter factory
- requirements, plan, decomposition, implementation, and review artifact paths
- implementation convoy id
- review lanes that ran
- proof commands or test summaries that were recorded
- publish outcome
- next human action

Record the final report path on the workflow root bead as both
`gc.build.final_report_path=<path>` and `gc.build.factory_run_path=<path>`.
Use `gc bd update "<workflow-root-id>" --set-metadata "gc.build.final_report_path=<absolute path>" --set-metadata "gc.build.factory_run_path=<absolute path>"`.
Do not use `gc bd update --metadata 'key=value'`; `--metadata` only accepts a JSON
object.

Before recording lifecycle success, resolve the launcher rig root from workflow
root metadata `gc.work_dir`. If it names an attempt worktree without the check,
walk to the nearest ancestor containing
`.gc/scripts/checks/build-artifact-valid.sh`. Read the exact claimed step ID
from the startup claim output and substitute it literally in the same shell
call; shell variables from earlier tool calls do not persist. Run:

```bash
CLAIMED_BEAD_ID=<exact-claimed-bead-id>; GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Repair the canonical final report until this check passes. Only after it passes
and the implementation and review evidence are approved, reconcile the
workflow root's successful lifecycle state in one update:

```bash
gc bd update <workflow-root-id> \
  --set-metadata 'gc.build.status=completed' \
  --set-metadata 'gc.build.finalize_status=completed' \
  --set-metadata 'gc.build.finalize_outcome=success' \
  --unset-metadata gc.blocked_reason \
  --unset-metadata gc.failure_class \
  --unset-metadata gc.build.repair_status \
  --unset-metadata gc.restart.entrypoint \
  --unset-metadata gc.restart.reason \
  --unset-metadata gc.restart.review_report_path \
  --unset-metadata gc.restart.review_fix_formula \
  --unset-metadata gc.restart.implementation_target
```

Then set the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"` and close
with `gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`. If validation or required
evidence fails, do not emit completed/success lifecycle metadata; close with
`gc.outcome=fail` and machine-readable failure state.

Do not publish from this step.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.final_report_path` against schema `gc.build.final-report.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
