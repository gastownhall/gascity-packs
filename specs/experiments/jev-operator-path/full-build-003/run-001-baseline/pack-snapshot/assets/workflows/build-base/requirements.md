This is the `build-base` requirements stage. Treat it as a virtual contract that concrete formulas may override.

Produce or reuse a requirements artifact under the build artifact root. The artifact must state the requested outcome, constraints, non-goals, acceptance criteria, and unresolved questions.

Read the requested task before writing the artifact. The workflow root's own
description is the formula description, not the task; the task text lives on
the beads tracked by the root's input convoy:

1. Read the claimed step bead's `gc.root_bead_id` (the claim result's
   `root_bead_id`), then read that workflow root with
   `gc bd show "<workflow-root-id>" --json`. If the JSON output is a
   one-element list, unwrap the first element before reading metadata.
2. Read root metadata `gc.input_convoy_id` (the runtime records the same id as
   `gc.var.convoy_id`) and read that convoy with
   `gc bd show "<input-convoy-id>" --json`, unwrapping a one-element list.
3. List the beads the convoy tracks with
   `gc convoy status "<input-convoy-id>" --json` and take every
   `children[].id`. If the convoy metadata has
   `gc.synthetic_kind=drain-unit-convoy`, its source bead is
   `gc.drain_member_id`.
4. Read each tracked bead with `gc bd show "<source-bead-id>" --json` and read
   its `title` and full `description`. A convoy without `gc.synthetic=true`
   was created by a person and may carry request text in its own title and
   description too; a synthetic convoy only wraps its tracked bead.

Reading the convoy and its tracked beads is context gathering, not claiming
work: do not update, close, or execute them.

The artifact must restate the requested behavior and every explicit constraint
from that source text (for example "do not change existing tests" or a required
verification command) as requirements. Acceptance criteria must describe
observable behavior of the requested change in the target repository, never
properties of the requirements artifact itself. List each source bead in
`trace.upstream` as `path: beads/<bead-id>` with `hash: bead:<bead-id>`.
Repository files may ground the requirements, but they never replace the
source task text.

If the root has no `gc.input_convoy_id`, the convoy tracks no readable bead,
or no source bead or convoy text states the requested work, do not invent a
task. In `headless` or `autonomous` mode, set `gc.outcome=fail`,
`gc.failure_class=missing-task-input`, and a concise `gc.failure_reason` on
the claimed step, then close it without writing an artifact. In `interactive`
mode, ask the user for the task.

Close this step only after the requirements path is recorded on the workflow
root bead. Use
`gc bd update "<workflow-root-id>" --set-metadata "gc.build.requirements_path=<absolute path>"`.
Do not use `gc bd update --metadata 'key=value'`; `--metadata` only accepts a JSON
object.
Before closing this step, set the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, then close
with `gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.requirements_path` (fallback `gc.var.requirements_path`) against schema `gc.build.requirements.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
