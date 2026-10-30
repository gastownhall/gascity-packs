This is the `build-from-plan-base` plan-repair stage.

Read the plan-review artifact, its verdict, the implementation plan at
`{{plan_path}}`, `planning_formula={{planning_formula}}`, and
`interaction_mode={{interaction_mode}}` from the workflow root metadata and
artifacts.

Normalize the verdict token to lowercase before comparing it. Only `approved`
or `proceed` is a pass. For either of these verdicts, do not
mutate the plan. Record `gc.build.plan_repair_status=not_needed`, preserve the
approved plan-review metadata, and close this step successfully. Only this
path releases `prepare-decompose`.

If the verdict is `changes_required`, `changes-required`, or
`proceed-with-fixes`, repair the implementation plan using the
selected planning formula and the concrete findings. Preserve requirement
traceability, assumptions, risks, and the recorded plan path. Record the
repair attempt and restart the continuation at `build-from-plan` so the
amended `plan.md` is reviewed again before decomposition. Record at least:

- `gc.build.plan_repair_status=repairable`
- `gc.restart.entrypoint=build-from-plan`
- `gc.restart.reason=plan_review_changes_required`
- `gc.restart.plan_path={{plan_path}}`
- `gc.restart.plan_review_path={{plan_review_path}}`
- `gc.restart.planning_formula={{planning_formula}}`

Do not release decomposition from `changes_required`, `changes-required`,
or `proceed-with-fixes`. Close this
step with failure metadata after recording the restart handoff so the current
graph cannot deadlock waiting for `plan-review` merely to complete; the
restarted continuation must run `plan-review` against the amended plan.

If the plan-review verdict is `blocked`, `questions`, `rejected`, missing,
unknown, or malformed, do
not invent an approval. Record `gc.build.plan_repair_status=blocked`,
`gc.outcome=fail`, and a machine-readable failure reason. Do not close the
workflow root with `gc.outcome=pass` from this stage.
