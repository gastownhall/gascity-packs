Use the assigned Superpowers branch-finalization skill materialized for this agent.

Use that skill as finalization guidance, then satisfy the Gas City artifact
contract below. In headless mode, select the non-publishing completion path
without asking which branch-finalization option to use.

Resolve the workflow root from the claimed step metadata. Read the canonical
final report path from workflow root metadata `gc.build.final_report_path` and
write the report there, normally `<artifact_root>/factory-run.md`. Do not
replace it with a path under the claimed attempt's worktree. Before closing,
confirm the final artifact paths, test evidence, review result, and publish
readiness, and record the build-base finalize outcome on the workflow root.

The final report must be Markdown with YAML front matter valid for
`gc.build.final-report.v1`. For a successful build, use top-level
`status: approved`; `completed` may describe the nested build outcome but is
not a schema-allowed top-level status. Include mapping objects for workflow,
methodology, and producer. The front matter must include the exact nested
fields `workflow.id`, `workflow.formula`, `methodology.pack`,
`methodology.name`, `producer.formula`, `producer.stage`, and a positive
integer `producer.attempt`; it must equal the claimed finalize stage's current
positive `gc.attempt`. Include both `trace.upstream` and
`trace.coverage`. Every upstream ID must appear once in `trace.coverage`; use
schema coverage statuses such as `covered`, not artifact statuses such as
`approved` or `completed`. If coverage is non-empty, include one Markdown
table whose `ID` and `Status` pairs exactly match `trace.coverage`.

Trace the canonical absolute `gc.build.implementation_summary_path` and
`gc.build.review_report_path` exactly once each, using a freshly computed
`sha256:<digest>` of each exact file. An earlier artifact, a byte-identical copy
at another path, or a path without its current digest is stale and must block
finalization.

Use these required second-level sections, in this order:

- `## Summary`
- `## Outcome`
- `## Artifacts`
- `## Remaining Risks`

Record the canonical report path on the workflow root as
`gc.build.final_report_path=<canonical final report path>`. Before setting the
claimed step to `gc.outcome=pass`, read the launcher rig root from the workflow
root bead's `gc.work_dir`. If that path names a per-step worktree without the
validator, use its nearest ancestor containing
`.gc/scripts/checks/build-artifact-valid.sh`; do not run the relative validator
from the claimed attempt's worktree. From the resolved launcher rig root, run
`GC_BEAD_ID=<claimed-step-id> .gc/scripts/checks/build-artifact-valid.sh` and
fix every validation error against the canonical root artifact.

Only after that validator passes and the artifact, test, review, and publish
readiness evidence all succeed, reconcile the workflow root in one update:

```bash
gc bd update <workflow-root-id> \
  --set-metadata 'gc.build.final_report_path=<canonical final report path>' \
  --set-metadata 'gc.build.status=completed' \
  --set-metadata 'gc.build.finalize_status=completed' \
  --set-metadata 'gc.build.finalize_outcome=success' \
  --unset-metadata gc.blocked_reason \
  --unset-metadata gc.failure_class
```

The root lifecycle value `gc.build.status=completed` is distinct from the final report's `status: approved`;
`approved` is the artifact schema value, not the workflow-root status
vocabulary.

Then set the claimed step to `gc.outcome=pass` and close it. Do not clear either
failure marker when validation or required evidence fails; a successful update
must explicitly unset them because metadata updates otherwise merge with stale
prepare-stage values.

Do not invoke provider-native subagents or upstream plugin runtime commands.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.final_report_path` against schema `gc.build.final-report.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair that canonical artifact in place instead of rewriting it or changing the root path. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
