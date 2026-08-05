This is the `build-from-plan-base` plan-review stage.

Review the implementation plan before decomposition. The verdict must map to
approved, questions, changes_required, or blocked, and it must honor
interaction_mode {{interaction_mode}}.

Write the plan-review artifact to `{{plan_review_path}}` when a concrete path was
supplied at launch; otherwise write it to a deterministic path under the artifact
root, `{{artifact_root}}/plan-review/report.md`. (`plan_review_path` is produced
by this stage, so at launch it is typically empty — do not treat the empty
interpolation as a real path.)

Close only after an approved or equivalent pass verdict is recorded, or after a
blocked/changes-required verdict is recorded with a concrete reason.

Before closing, PROMOTE the plan-review artifact path to the workflow root so the
downstream decompose stage can read it at runtime (symmetric with
`gc.build.plan_path`; dip-5hkepo). Record the absolute path you actually wrote:

`bd update "<workflow-root-id>" --set-metadata "gc.build.plan_review_path=<absolute path>" --set-metadata "gc.var.plan_review_path=<absolute path>"`

Do not use `bd update --metadata 'key=value'`; `--metadata` only accepts a JSON
object. Before closing this step, set the claimed step outcome with
`bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, then close with
`bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `bd close`.
