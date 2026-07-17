Translate the approved plan at `{{plan_path}}` and optional context
`{{context_path}}` into a Compound Engineering implementation convoy. Read the
canonical plan from workflow root metadata `gc.build.plan_path` (fallback
`gc.var.plan_path`) when the rendered plan path is blank.

Drain topology constraint: every work item runs in its own isolated,
non-integrated source-anchor worktree. Therefore each work item must be a
complete, independently verifiable vertical product slice. Do not create
package-only, implementation-only, test-only, or cleanup-only members whose
correctness depends on another member's unmerged commit. If the requested
change is one smallest coherent behavior, create one work item instead of an
artificial horizontal split.

Create the implementation work-item beads first. Each item must define one
complete, independently verifiable product slice and preserve the actual
requirement and plan identifiers it covers. Then create one new non-empty
implementation convoy from all captured bead IDs in one command:

```bash
gc convoy create "compound implementation for <workflow-root-id>" <all-work-item-id...> --json
```

Do not pass `--owned`: owned convoys use a manual lifecycle and do not
auto-close after their members close, which blocks the downstream build gate.
Parse the implementation convoy ID from the JSON response. Do not reuse the
launch convoy or the workflow root bead as the implementation convoy.

Record the new convoy ID on the workflow root bead as both
`gc.input_convoy_id=<implementation-convoy-id>` and
`gc.build.implementation_convoy_id=<implementation-convoy-id>`. Do not record
these only on the current step. Before closing, verify both metadata keys on the
workflow root bead identify the new implementation convoy.

Read the exact decomposition path from workflow root metadata
`gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) and write
the canonical artifact there. Do not substitute an attempt-local path. The
artifact is Markdown with YAML front matter, not JSON. Its first line must be `---`,
and its front matter must end with another line containing exactly `---`
before the body. Use nested mappings with this shape:

```yaml
---
schema: gc.build.decomposition.v1
workflow:
  id: <workflow-root-id>
  formula: <root-workflow-formula>
methodology:
  pack: compound-engineering
  name: compound-decomposition
producer:
  formula: <executing-formula>
  stage: decompose
  attempt: <positive integer>
status: approved
trace:
  upstream:
    - path: <approved-plan-path>
      hash: sha256:<approved-plan-digest>
      ids: [<actual-source-id>]
  coverage:
    - id: <actual-source-id>
      status: covered
---
```

Every `trace.upstream` entry must be a mapping with a non-empty `path` and a
scheme-qualified `hash`. Preserve actual source IDs verbatim; never invent,
substitute, or renumber them. Account for each declared upstream ID exactly
once in `trace.coverage`. If no source declares IDs, omit `ids` and use
`coverage: []`. Use only schema coverage statuses, and include a non-empty
`rationale` for every status other than `covered`.

When coverage is non-empty, include one Markdown coverage table whose `ID` and `Status`
pairs exactly match `trace.coverage`:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Replace the example with actual IDs. When coverage is empty, omit the table or
include only its header and separator; never emit a placeholder data row.

Use these required second-level sections in this exact order:

- `## Summary`
- `## Selected Downstream Formulas`
- `## Implementation Convoy`
- `## Work Items`

Under `## Implementation Convoy`, record the new convoy ID and ordered member
IDs. Under `## Work Items`, record each work-item bead ID, dependencies,
accepted source IDs, plan section, affected files, first verification command,
and expected final proof command.

Record `gc.build.decomposition_path=<absolute canonical decomposition path>` on
the workflow root bead. Before closing, read the launcher rig root from workflow
root metadata `gc.work_dir`. If needed, walk to the nearest ancestor containing
`.gc/scripts/checks/build-artifact-valid.sh`. From that launcher rig root run:

Read the exact current bead ID from the startup claim output. In the same shell
invocation, substitute it literally for the placeholder below; variables from
earlier tool calls do not persist.

```bash
export CLAIMED_BEAD_ID='<exact-current-bead-id>'
GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Repair every reported error in the exact canonical artifact, rerun the check
until it passes, and verify the two convoy metadata fields before setting
`gc.outcome=pass`.

Do not invoke provider-native subagents or upstream plugin runtime commands.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) against schema `gc.build.decomposition.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
