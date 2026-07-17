Create the gstack implementation convoy.

Read the approved plan and decompose it into implementation beads under the
workflow root bead. Each bead must map to one vertical slice and include
acceptance criteria, files or modules likely affected, first verification
command, and expected proof command.

Drain topology constraint: every work item runs in its own isolated,
non-integrated source-anchor worktree. Therefore each work item must be a
complete, independently verifiable vertical product slice. Do not create
package-only, implementation-only, test-only, or cleanup-only members whose
correctness depends on another member's unmerged commit. If the requested
change is one smallest coherent behavior, create one work item instead of an
artificial horizontal split.

Create the implementation work-item beads first and capture every returned ID.
These beads are inputs to the implementation drain, not directly routed work.
Create each one open, unassigned, and unrouted, with metadata
`gc.kind=implementation`, `gc.accepts_from={{implementation_target}}`, and
`gc.root_bead_id=<workflow-root-id>`. Use the JSON-object form of `--metadata`:

```bash
gc bd create --title "<work-item-title>" --description "<work-item-description>" \
  --type task \
  --metadata '{"gc.root_bead_id":"<workflow-root-id>","gc.kind":"implementation","gc.accepts_from":"{{implementation_target}}"}' \
  --json
```

Do not pass `--assignee` and do not set `gc.routed_to` on these work items; the
downstream drain owns their routing and worktree lifecycle. Read every created
work item back with `gc bd show <work-item-id> --json` and require `status=open`,
an empty or absent `assignee`, an empty or absent `gc.routed_to`, and the exact
`gc.kind` and `gc.accepts_from` metadata above before creating the convoy.

Each work item must name the launch source target ID or IDs it implements under
`Source Targets`; across all work items, every direct member of the launch
convoy from `gc.var.convoy_id` must be accounted for. Then create one new
non-empty implementation convoy in one command, with the descriptive name as
the first positional argument and every captured work-item ID after it:

```bash
gc convoy create "gstack implementation for <workflow-root-id>" <all-work-item-id...> --json
```

Do not run `gc convoy create <first-work-item-id> ...`: the CLI interprets its
first positional argument as the convoy name and silently omits that work item
from membership. Do not reuse the workflow's launch or source convoy, and do
not add members later in a second command.

Parse both `convoy_id` and `issue_ids` from the create response. Require
`issue_ids` to be exactly equal to the complete captured work-item ID list,
with no missing, extra, or duplicate ID. Run
`gc convoy status <implementation-convoy-id> --json` and independently require its `children`
IDs to be exactly equal to the same list. Record the comma-separated complete
list on the workflow root as
`gc.build.implementation_member_ids=<work-item-id-1,work-item-id-2,...>`.

Record the new convoy ID on the workflow root bead as both
`gc.input_convoy_id=<implementation-convoy-id>` and
`gc.build.implementation_convoy_id=<implementation-convoy-id>`. Do not record
these only on the current step. Before closing, verify both workflow root
metadata values identify the new implementation convoy and the member metadata
matches the status response exactly. Downstream summary and final gates require
that this same convoy and every exact recorded member later reach
`status=closed`; a closed subset is not successful implementation.

Do not copy review-lane procedure into implementation beads. The convoy should
describe product work; `gstack-work` carries the execution process.

Read the exact decomposition path from workflow root metadata
`gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) and write
the canonical artifact there. It must be Markdown with YAML front matter, not
JSON. Its first line must be `---`, with a closing `---` before the Markdown
body. Use nested YAML mappings with this top-level shape:

```yaml
---
schema: gc.build.decomposition.v1
workflow:
  id: <workflow-root-id>
  formula: <root-workflow-formula>
methodology:
  pack: gstack
  name: gstack-decomposition
producer:
  formula: gstack-build
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

Every `trace.upstream` entry must contain `path` and a scheme-qualified `hash`.
Preserve actual source IDs verbatim; never invent, substitute, or renumber
them. Every declared upstream ID must appear exactly once in `trace.coverage`;
when none are declared, omit `ids` and use `coverage: []`. Every non-`covered`
row needs a rationale. Include one Markdown coverage table. The table columns
are `ID` and `Status`. Their pairs must exactly match the YAML coverage:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Only include the example data row when coverage is non-empty, and replace the
placeholder with an actual ID. When coverage is empty, do not add a data row;
omit the table or use only its header and separator.

Use these schema-required second-level headings in this exact order:

- `## Summary`
- `## Selected Downstream Formulas`
- `## Implementation Convoy`
- `## Work Items`

Record each work-item bead ID as a `### <work-item-id>: <title>` heading, plus
its dependency, `Source Targets`, accepted requirement IDs, plan section,
affected files, first verification command, and expected proof command under
`## Work Items`. Record the new convoy ID and its members under
`## Implementation Convoy`.

Record `gc.build.decomposition_path=<absolute path>` on the workflow root bead.
Before closing, resolve the launcher rig root from workflow root metadata
`gc.work_dir`, walk to the nearest ancestor containing the canonical check when
needed, and read the exact current bead ID from the startup claim output.
Substitute that ID literally below; shell variables from earlier tool calls do
not persist. Run:

```bash
GC_BEAD_ID=<exact-claimed-bead-id> <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Fix every validation error in the canonical artifact and verify both convoy
metadata fields before setting `gc.outcome=pass`.

Close with `gc.outcome=pass`.

Do not invoke provider-native subagents. Gas City graph lanes own fanout.

Artifact validation: this stage is gated by the shipped `../assets/scripts/checks/gstack-build-state-valid.sh`, which first validates the artifact recorded at `gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) against schema `gc.build.decomposition.v1`, then verifies launch-source accounting, the descriptive convoy name, exact recorded membership, and that every member remains an open, unassigned, unrouted drain input. On repair attempts (`gc.attempt` greater than 1), read validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact and runtime metadata in place. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable failure metadata that blocks downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
