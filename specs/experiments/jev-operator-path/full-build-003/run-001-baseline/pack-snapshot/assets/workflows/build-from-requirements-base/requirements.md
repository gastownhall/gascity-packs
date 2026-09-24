This is the `build-from-requirements-base` requirements stage.

Produce or reuse the requirements artifact at `{{requirements_path}}` when
provided; otherwise write the default requirements artifact under
`{{artifact_root}}`.

When writing a new artifact, take the task from the input convoy as described
below. This continuation may launch without a target; when the workflow root
has no `gc.input_convoy_id`, the task text must come from the
`{{context_path}}` bundle instead, and the fail-closed rule below applies when
neither source states the requested work.

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

The requirements artifact must use the base requirements contract, stable IDs,
example mapping, acceptance criteria, open questions, out-of-scope notes, and
approval state. Close only after the requirements path and content hash are
recorded for the inherited plan suffix.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.requirements_path` (fallback `gc.var.requirements_path`) against schema `gc.build.requirements.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
