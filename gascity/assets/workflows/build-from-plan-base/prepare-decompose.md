This is the `build-from-plan-base` handoff into the inherited decompose suffix.
It is the FAIL-LOUD guard for decompose inputs (dip-5hkepo): decompose must never
run on empty plan_path / plan_review_path.

Resolve the decompose inputs at RUNTIME from the workflow ROOT var store — do NOT
trust the instantiation-frozen `{{plan_path}}`/`{{plan_review_path}}`, which mint
empty when the plan/plan-review stages produce their paths mid-flow. Resolve
`<workflow-root-id>` via `gc.root_bead_id` on this step bead (a bead with no
`gc.root_bead_id` is its own root).

The claimed bead id is `$GC_BEAD_ID`. Run
`.gc/scripts/checks/decompose-inputs-present.sh` with that environment unchanged
and capture its exit code and single-line diagnostic. Never rewrite or bypass the
guard. Do not create implementation beads in this handoff step.

If the script exits 0 (both `gc.build.plan_path` and `gc.build.plan_review_path`
are present and non-empty on the root — fallbacks `gc.var.plan_path` /
`gc.var.plan_review_path`), the plan and plan-review artifacts exist and the
plan-review verdict already approved decomposition (the upstream
plan-review-approved gate enforced that). Set the claimed step
`gc.outcome=pass` and close it with reason
`decompose inputs resolved on root; handoff complete`. The inherited
`build-from-decompose-base` decompose suffix may become ready only after this
close.

If the script exits non-zero, DO NOT close this step. The build halts loudly
here so the task-decomposer never activates on empty inputs. Update only the
claimed step, in one operation, with:

- status `blocked`
- `gc.outcome=blocked`
- `gc.failure_class=decompose-inputs-unresolved`
- append the guard's single-line diagnostic to the bead notes

Read the claimed step back and verify it is `status=blocked` and is NOT closed.
Then page the mayor with subject
`BLOCKED: decompose inputs unresolved` and a body containing the step bead id,
workflow-root id, and the guard diagnostic. The open, blocked step is the
barrier: the inherited decompose beads depend on it and therefore remain blocked.
Do NOT create or route a replacement decomposition bead, implementation convoy,
or work bead.

Use `gc bd update <id> --set-metadata key=value` for metadata and `--status
blocked` for the halt state. Close with `gc bd close <id> --reason <reason>` only
on the inputs-present path. Do not invoke provider-native subagents. Your exact
final action must be `gc runtime drain-ack`; emit no text after it.
