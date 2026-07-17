Create the BMAD PRD requirements artifact.

Use the installed `bmad-prd` skill as a methodology reference only. Gas City
owns orchestration, persistence, retries, and headless execution. Do not greet
or present menus, and do not wait for user input in headless mode. Never wait
for an interactive BMAD selection; make the safest evidence-backed choice and
record unresolved ambiguity in the open-questions section.

Resolve the actual build request before applying BMAD terminology. Read the
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

Read the exact canonical output path from workflow root metadata
`gc.build.requirements_path` (fallback `gc.var.requirements_path`). Write the
artifact at that path and record its absolute path on the workflow root as
`gc.build.requirements_path`. Never replace it with a lane-local or
attempt-local path.

Write Markdown with YAML front matter valid for
`gc.build.requirements.v1`, not freeform prose or JSON. The artifact's first line must be `---`,
followed by a closing `---` before the Markdown body. Use nested YAML
mappings with this top-level shape:

```yaml
---
schema: gc.build.requirements.v1
workflow:
  id: <workflow-root-id>
  formula: bmad-build
methodology:
  pack: bmad
  name: bmad-prd
producer:
  formula: bmad-build
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

Every `trace.upstream` entry must contain `path` and a scheme-qualified `hash`.
Preserve actual source IDs verbatim; never invent, substitute, or renumber
them. Every declared upstream ID must appear exactly once in `trace.coverage`.
When no source declares IDs, omit `ids` and use `coverage: []`. Every
non-`covered` coverage row requires a rationale.

Include one Markdown coverage table whose `ID` and `Status` pairs exactly match
the YAML coverage:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Only include the example data row when coverage is non-empty, replacing the
placeholder with an actual ID. When coverage is empty, omit the table or use
only its header and separator; do not add a placeholder data row.

Use these schema-required second-level headings in this exact order:

- `## Problem Statement`
- `## W6H`
- `## User Stories`
- `## Technical Stories`
- `## Behavior Requirements`
- `## Example Mapping`
- `## Acceptance Criteria`
- `## Out Of Scope`
- `## Open Questions`

Give each requirement, rule, example, and acceptance criterion a stable actual
source ID when one is present in the input, and preserve those IDs through the
coverage table. Do not fabricate requirement IDs merely to make a table
non-empty.

Before closing, resolve the launcher rig root from workflow root metadata
`gc.work_dir`. If it names an attempt worktree without the validator, walk to
the nearest ancestor containing
`.gc/scripts/checks/build-requirements-source-valid.sh`. Read the exact current bead ID
from the startup claim output and assign it literally in the same shell call;
shell variables from earlier tool calls do not persist. Run:

```bash
CLAIMED_BEAD_ID=<exact-claimed-bead-id>; GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-requirements-source-valid.sh
```

Fix every validation error at the canonical path before setting
`gc.outcome=pass`. On repair attempts (`gc.attempt` greater than 1), read
validator errors from `gc.attempt_log` on the dependent validation-loop control
bead and repair the same artifact in place. Two bounded repair attempts follow
the first failure; exhaustion must close with `gc.outcome=fail` and
machine-readable failure metadata.

Do not invoke provider-native subagents or upstream BMAD runtime commands.
