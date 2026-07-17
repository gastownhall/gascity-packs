Run garrytan/gstack office-hours intake for this build.

Use the gstack sprint model: Think -> Plan -> Build -> Review -> Test -> Ship -> Reflect.
The upstream vocabulary is office-hours, plan-ceo-review,
plan-eng-review, plan-design-review, plan-devex-review, review, qa, cso, ship,
land-and-deploy, and document-release. In Gas City, those become graph lanes.

Current interaction_mode is {{interaction_mode}}. In interactive mode, ask one
focused question at a time when demand, status quo, user specificity, narrowest
wedge, observation, or future-fit is missing. In autonomous mode, write the
best requirements artifact from available context and record assumptions.

Resolve the actual build request before drafting methodology content. Read the
workflow root bead's reserved `gc.var.convoy_id` as `<launch-convoy-id>`, then
run `gc convoy status <launch-convoy-id> --json`. Treat every direct
launch-convoy member as a source target. Read each source target with `gc bd
show <source-target-id> --json` and use its title, description, acceptance
criteria, and constraints as the authoritative requested outcome. The workflow
root description and gstack formula describe process, not product scope. Never
replace the source target with a plan for improving the gstack workflow itself.
If the launch convoy is missing, empty, or unreadable, fail closed instead of
inventing requirements.

Trace every direct launch-convoy member exactly once as an upstream source
using `path: beads/<source-target-id>` and `hash: bead:<source-target-id>`.
When a source target contains its own requirement IDs, preserve those IDs in
`ids` and coverage as described below. Source targets without declared
requirement IDs still require the exact bead path/hash entry; do not trace only
the workflow root or launch convoy.

Read the exact requirements path from workflow root metadata
`gc.build.requirements_path` (fallback `gc.var.requirements_path`) and write the
canonical artifact there. Do not substitute a path under this attempt's
worktree. The artifact must be Markdown with YAML front matter, not JSON. Its
first line must be `---`, and the front matter must end with another line that
is exactly `---` before the Markdown body.

Use nested YAML mappings with this top-level shape:

```yaml
---
schema: gc.build.requirements.v1
workflow:
  id: <workflow-root-id>
  formula: <root-workflow-formula>
methodology:
  pack: gstack
  name: office-hours
producer:
  formula: gstack-build
  stage: requirements
  attempt: <positive integer>
status: approved
trace:
  upstream:
    - path: beads/<source-target-id>
      hash: bead:<source-target-id>
  coverage: []
---
```

Every `trace.upstream` entry must contain `path` and a scheme-qualified `hash`
such as `bead:<id>`, `sha256:<digest>`, or `git:<revision>`. When an upstream
source declares IDs, preserve its actual source IDs verbatim; never invent,
substitute, or renumber IDs. Include every declared ID exactly once in
`trace.coverage`. When the source declares no IDs, omit `ids` and use
`coverage: []`. Use only the schema coverage statuses `covered`,
`not_applicable`, `deferred`, `blocked`, `out_of_scope`, or `superseded`, and
include a non-empty `rationale` for every status other than `covered`.

Include one Markdown coverage table whose `ID` and `Status` pairs exactly match
`trace.coverage`:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Only include the example data row when coverage is non-empty, and replace the
placeholder with an actual ID. When coverage is empty, do not add a data row;
omit the table or use only its header and separator.

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

Within those sections include the goal, demand evidence, current workaround,
target user, narrowest wedge, future-fit, constraints, acceptance criteria,
non-goals, and unresolved questions. In headless mode, record ambiguity in
`## Open Questions` instead of asking a human.

Record the canonical absolute path back on the workflow root bead as
`gc.build.requirements_path=<absolute path>`. Before closing, read the launcher rig root
from workflow root metadata `gc.work_dir`. If it points at a step
worktree without the check, use the nearest ancestor containing
`.gc/scripts/checks/build-artifact-valid.sh`. Read the exact current bead ID
from the startup claim output and substitute it literally below; shell
variables from earlier tool calls do not persist. Then run:

```bash
GC_BEAD_ID=<exact-claimed-bead-id> <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Fix every validation error in the canonical artifact before setting
`gc.outcome=pass`.

Close with `gc.outcome=pass` and the requirements artifact path.

Do not invoke provider-native subagents. This Gas City lane is the office-hours
worker for the build.

Artifact validation: this stage is gated by the shipped `../assets/scripts/checks/gstack-build-state-valid.sh`, which first runs the shared schema validator for the artifact recorded at `gc.build.requirements_path` (fallback `gc.var.requirements_path`) and then verifies exact launch-source trace coverage. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
