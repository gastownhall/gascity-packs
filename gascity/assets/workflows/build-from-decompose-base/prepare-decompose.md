This is the `build-from-decompose-base` decompose handoff step. It is the
FAIL-LOUD guard for decompose inputs (dip-5hkepo): decompose must never run on
empty plan_path / plan_review_path.

Concrete rule: concrete methodology packs extend this base rather than copying the suffix graph.

Validate the prerequisite inputs before any side effects. `artifact_root`,
`context_path`, `requirements_path`, `decomposition_path`,
`decomposition_formula`, `drain_policy`, `interaction_mode`, and `review_mode`
are provided-upfront launch inputs. Resolve `plan_path` and `plan_review_path` at
RUNTIME from the workflow ROOT var store — do NOT trust the instantiation-frozen
`{{plan_path}}`/`{{plan_review_path}}`. Resolve `<workflow-root-id>` via
`gc.root_bead_id` on this step bead (a bead with no `gc.root_bead_id` is its own
root).

The claimed bead id is `$GC_BEAD_ID`. Run
`.gc/scripts/checks/decompose-inputs-present.sh` with that environment unchanged
and capture its exit code and single-line diagnostic. Never rewrite or bypass the
guard. Do not rerun requirements, plan, or plan-review. This continuation is valid
only when the supplied requirements, implementation plan, and plan-review
artifacts exist and the plan-review artifact records approval or an equivalent
pass verdict.

If the script exits 0 (both `gc.build.plan_path` and `gc.build.plan_review_path`
are present and non-empty on the root — fallbacks `gc.var.plan_path` /
`gc.var.plan_review_path`), record
`gc.build.continuation_entrypoint=decompose` when this suffix is launched
directly, set the claimed step `gc.outcome=pass`, and close it only after the
decompose stage can create or reuse the decomposition artifact and implementation
convoy.

If the script exits non-zero, DO NOT close this step. The build halts loudly here
so the task-decomposer never activates on empty inputs. Update only the claimed
step, in one operation, with:

- status `blocked`
- `gc.outcome=blocked`
- `gc.failure_class=decompose-inputs-unresolved`
- append the guard's single-line diagnostic to the bead notes

Read the claimed step back and verify it is `status=blocked` and is NOT closed.
Then page the mayor with subject `BLOCKED: decompose inputs unresolved` and a body
containing the step bead id, workflow-root id, and the guard diagnostic. The open,
blocked step is the barrier: the decompose beads depend on it and therefore remain
blocked. Do NOT create or route a replacement decomposition bead, implementation
convoy, or work bead.

Use `gc bd update <id> --set-metadata key=value` for metadata and `--status
blocked` for the halt state. Close with `gc bd close <id> --reason <reason>` only
on the inputs-present path. Do not invoke provider-native subagents. Your exact
final action must be `gc runtime drain-ack`; emit no text after it.
