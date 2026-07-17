Create the BMAD architecture and implementation plan artifact.

Treat the installed `bmad-create-architecture` skill as a methodology reference only.
Gas City owns orchestration and the output contract. Do not greet or present menus,
and do not wait for user input in headless mode. Never wait for an interactive
selection; make conservative decisions from repository evidence and record
unresolved choices in the plan.

Read the approved requirements artifact and repository state. Read the exact
canonical output path from workflow root metadata `gc.build.plan_path`
(fallback `gc.var.plan_path`), write the artifact there, and record its
absolute path on the workflow root as `gc.build.plan_path`. Never replace it
with a lane-local or attempt-local path.

Write Markdown with YAML front matter valid for `gc.build.plan.v1`, not JSON.
The artifact's first line must be `---`, followed by a closing `---` before the Markdown
body. Use nested YAML mappings with this top-level shape:

```yaml
---
schema: gc.build.plan.v1
workflow:
  id: <workflow-root-id>
  formula: bmad-build
methodology:
  pack: bmad
  name: bmad-create-architecture
producer:
  formula: bmad-build
  stage: plan
  attempt: <positive integer>
status: approved
trace:
  upstream:
    - path: <approved-requirements-path>
      hash: sha256:<requirements-digest>
      ids: [<actual-source-id>]
  coverage:
    - id: <actual-source-id>
      status: covered
---
```

Every `trace.upstream` entry must contain `path` and a scheme-qualified `hash`.
Preserve actual source IDs verbatim; never invent, substitute, or renumber
them. Every declared ID must appear exactly once in `trace.coverage`; when no
source declares IDs, omit `ids` and use `coverage: []`. Give every
non-`covered` row a rationale.

Include one Markdown coverage table whose `ID` and `Status` pairs exactly match
the YAML coverage:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Only include the example data row when coverage is non-empty, replacing the
placeholder with an actual ID. When coverage is empty, omit the table or use
only its header and separator; do not add a placeholder data row.

Use these schema-required second-level headings in this exact order:

- `## Summary`
- `## Current System`
- `## Proposed Implementation`
- `## Non-Goals`
- `## Verification`

Document architecture decisions, affected modules, interfaces, migration or
rollout considerations, negative space, and concrete verification commands.

Before closing, resolve the launcher rig root from workflow root metadata
`gc.work_dir`. If it names an attempt worktree without the validator, walk to
the nearest ancestor containing
`.gc/scripts/checks/build-artifact-valid.sh`. Read the exact current bead ID
from the startup claim output and assign it literally in the same shell call;
shell variables from earlier tool calls do not persist. Run:

```bash
CLAIMED_BEAD_ID=<exact-claimed-bead-id>; GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Fix every validation error at the canonical path before setting
`gc.outcome=pass`. On repair attempts (`gc.attempt` greater than 1), read
validator errors from `gc.attempt_log` on the dependent validation-loop control
bead and repair the same artifact in place. Two bounded repair attempts follow
the first failure; exhaustion must close with `gc.outcome=fail` and
machine-readable failure metadata.

Do not invoke provider-native subagents or upstream BMAD runtime commands.
