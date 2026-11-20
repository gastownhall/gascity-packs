This is the `build-from-plan-base` plan-review stage.

Review the implementation plan before decomposition. The verdict must map to
approved, questions, changes_required, or blocked, and it must honor
interaction_mode {{interaction_mode}}.

Write the plan-review artifact to `{{plan_review_path}}` when supplied;
otherwise write it under `{{artifact_root}}`, and record that path on the
workflow root as `gc.build.plan_review_report_path` with
`gc bd update "<workflow-root-id>" --set-metadata "gc.build.plan_review_report_path=<absolute path>"`.
Do not write or overwrite `gc.build.review_report_path`; that key is reserved
for the implementation review.

The artifact is Markdown with YAML front matter valid for
`gc.build.plan-review.v1` (`gascity/schemas/build/plan-review.v1.yaml`):
`schema: gc.build.plan-review.v1`, `workflow`, `methodology`, `producer`
(`stage: plan-review`), `status`, `trace`, and a single `verdict` token from
the schema's closed vocabulary. `approved` or `proceed` release decomposition;
`proceed-with-fixes`, `changes-required`, `changes_required`, `questions`,
`blocked`, and `rejected` do not. A conditional verdict is not a pass: amend the
plan and re-review instead of downgrading a required finding to prose. Include
the `Verdict`, `Findings`, and `Verification` sections. Validate with
`validate_build_artifact.py --schema gc.build.plan-review.v1 --path <artifact>`
before closing.

Close only after an approved or equivalent pass verdict is recorded, or after a
blocked/changes-required verdict is recorded with a concrete reason.
