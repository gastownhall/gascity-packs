Use the assigned Compound Engineering brainstorm skill materialized for this
agent. Apply its discovery discipline to the build target and optional context,
but normalize its result into the Gas City build artifact described below. Do
not use the stock `docs/brainstorms/` output as the build artifact, and do not
write HTML or JSON.

Resolve the actual build request before applying the methodology. Read the
workflow root bead's reserved `gc.var.convoy_id` as `<launch-convoy-id>`, run
`gc convoy status <launch-convoy-id> --json`, and treat every direct
launch-convoy member as a source target. Run `gc bd show <source-target-id> --json`
for each source and use its title, description, acceptance criteria, and
constraints as authoritative product scope. The workflow and formula roots
describe process, not requested product behavior. If the launch convoy is
missing, empty, ambiguous, or unreadable, fail closed instead of inventing
requirements.

Trace every direct launch-convoy member exactly once using
`path: beads/<source-target-id>` and `hash: bead:<source-target-id>`. Do not
substitute the workflow root, prepare step, convoy, or an empty context file.
Preserve IDs declared by a source verbatim; do not attribute invented IDs to a
source that did not declare them.

Read the exact requirements path from workflow root metadata
`gc.build.requirements_path` (fallback `gc.var.requirements_path`). Write the
normalized artifact to that path; do not substitute a per-attempt path.

The artifact is Markdown with YAML front matter. Its first line must be `---`,
and the front matter must end with another line containing exactly `---` before
the Markdown body. Use nested mappings with this shape:

```yaml
---
schema: gc.build.requirements.v1
workflow:
  id: <workflow-root-id>
  formula: compound-build
methodology:
  pack: compound-engineering
  name: ce-brainstorm
producer:
  formula: compound-build
  stage: requirements
  attempt: <positive integer>
status: approved
trace:
  upstream:
    - path: beads/<source-target-id>
      hash: bead:<source-target-id>
      ids: [<actual-source-id>]
  coverage:
    - id: <actual-source-id>
      status: covered
---
```

Every `trace.upstream` entry must be a mapping with a non-empty `path` and a
scheme-qualified `hash`, such as `bead:<id>`, `git:<revision>`, or
`sha256:<digest>`. Preserve actual source IDs verbatim; never invent,
substitute, or renumber them. If an upstream entry lists IDs, account for each
ID exactly once in `trace.coverage`. If no source declares IDs, omit `ids` and
use `coverage: []`. Use only schema coverage statuses: `covered`,
`not_applicable`, `deferred`, `blocked`, `out_of_scope`, or `superseded`.
Every non-`covered` entry needs a non-empty `rationale`.

When coverage is non-empty, include one Markdown coverage table whose `ID` and `Status`
pairs exactly match `trace.coverage`:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

The example data row is illustrative. Replace it with actual IDs when coverage
is non-empty. When coverage is empty, omit the table or include only its header
and separator; never emit a placeholder data row.

Use these required second-level sections in this exact order:

- `## Problem Statement`
- `## W6H`
- `## User Stories`
- `## Technical Stories`
- `## Behavior Requirements`
- `## Example Mapping`
- `## Acceptance Criteria`
- `## Out Of Scope`
- `## Open Questions`

Preserve Compound Engineering requirement and assumption identifiers inside
that normalized structure. After writing it, update the workflow root bead
with:

- `gc.build.requirements_path=<requirements artifact path>`
- `gc.build.requirements_status=approved`
- `gc.build.requirements_summary=<one-sentence summary>`

Before closing, read the launcher rig root from workflow root metadata
`gc.work_dir`. If needed, walk to the nearest ancestor containing
`.gc/scripts/checks/build-requirements-source-valid.sh`. From that launcher rig root run:

Read the exact current bead ID from the startup claim output. In the same shell
invocation, substitute it literally for the placeholder below; variables from
earlier tool calls do not persist.

```bash
export CLAIMED_BEAD_ID='<exact-current-bead-id>'
GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-requirements-source-valid.sh
```

Repair every reported error in the exact canonical artifact and rerun the check
until it passes. Close this step only after workflow root metadata and this step
metadata record the same approved requirements outcome.

Do not invoke provider-native subagents or upstream plugin runtime commands.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-requirements-source-valid.sh`, which validates the artifact recorded at `gc.build.requirements_path` (fallback `gc.var.requirements_path`) against schema `gc.build.requirements.v1` and requires an exact trace for every direct launch-convoy source. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
