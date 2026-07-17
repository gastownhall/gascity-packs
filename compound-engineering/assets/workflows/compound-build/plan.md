Use the assigned Compound Engineering planning skill materialized for this
agent. Apply its repository research and planning discipline to the approved
requirements, but normalize its result into the Gas City build artifact below.
Do not use a stock `docs/plans/` document as the canonical build artifact, and
do not write HTML or JSON.

Read the requirements artifact from workflow root metadata
`gc.build.requirements_path` (fallback `gc.var.requirements_path`). Read the
exact canonical plan path from `gc.build.plan_path` (fallback
`gc.var.plan_path`) and write the plan there. Do not substitute a path under
this attempt's worktree.

The plan is Markdown with YAML front matter. Its first line must be `---`, and
the front matter must end with another line containing exactly `---` before the
Markdown body. Use nested mappings with this shape:

```yaml
---
schema: gc.build.plan.v1
workflow:
  id: <workflow-root-id>
  formula: <root-workflow-formula>
methodology:
  pack: compound-engineering
  name: ce-plan
producer:
  formula: compound-build
  stage: plan
  attempt: <positive integer>
status: approved
trace:
  upstream:
    - path: <requirements-artifact-path>
      hash: sha256:<requirements-artifact-digest>
      ids: [<actual-source-id>]
  coverage:
    - id: <actual-source-id>
      status: covered
---
```

Every `trace.upstream` entry must be a mapping with a non-empty `path` and a
scheme-qualified `hash`, such as `bead:<id>`, `git:<revision>`, or
`sha256:<digest>`. Preserve actual source IDs verbatim; never invent,
substitute, or renumber them. Account for each declared upstream ID exactly
once in `trace.coverage`. If no source declares IDs, omit `ids` and use
`coverage: []`. Use only schema coverage statuses: `covered`,
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

- `## Summary`
- `## Current System`
- `## Proposed Implementation`
- `## Non-Goals`
- `## Verification`

Preserve Compound Engineering requirement and assumption identifiers. Include
the recommended approach, alternatives considered, concrete task boundaries,
affected files, release risks, and exact focused and final verification
commands. Use `status: approved` only when the plan is internally complete
enough for the plan-review fanout.

After writing the artifact, update the workflow root bead with:

- `gc.build.plan_path=<absolute canonical plan artifact path>`
- `gc.build.plan_status=approved`
- `gc.build.plan_summary=<one-sentence summary>`

Before closing, read the launcher rig root from workflow root metadata
`gc.work_dir`. If needed, walk to the nearest ancestor containing
`.gc/scripts/checks/build-artifact-valid.sh`. From that launcher rig root run:

Read the exact current bead ID from the startup claim output. In the same shell
invocation, substitute it literally for the placeholder below; variables from
earlier tool calls do not persist.

```bash
export CLAIMED_BEAD_ID='<exact-current-bead-id>'
GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Repair every reported error in the exact canonical artifact and rerun the check
until it passes. Close only after workflow root metadata and this step metadata
record the same approved plan outcome.

Do not invoke provider-native subagents or upstream plugin runtime commands. If
upstream methodology would require document-review or research subagents,
record the needed graph lanes as required follow-up.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.plan_path` (fallback `gc.var.plan_path`) against schema `gc.build.plan.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
