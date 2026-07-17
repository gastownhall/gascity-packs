Implement the assigned BMAD story in its authoritative worktree.

Read `gc.build.implementation_source_anchor_id` and
`gc.build.implementation_worktree_path` from the workflow root. Re-read the
source anchor and require its `work_dir` to equal that absolute, existing git
worktree. Set `WORKTREE` to the recorded path, run `cd "$WORKTREE"`, and verify
`pwd -P` equals `$WORKTREE` before any source read, edit, test, file hash,
`git add`, or commit. Do not use workflow root metadata `gc.work_dir` as the
implementation location; it is the launcher rig root used for validation.

Read `gc.build.story_development_artifact_root` and
`gc.build.story_development_context_path` from the workflow root. Require both
to be absolute, require the context path to be contained by the story artifact
root, and require the context file to exist. Read that exact context file and
require its source anchor, worktree, summary path, and story/requirement IDs to
match workflow-root metadata. Block on a missing or mismatched context rather
than inferring scope from this attempt bead or unrelated repository files.

Use the installed `bmad-quick-dev` and `bmad-dev-story` skills as methodology
guidance. Treat BMAD's request to hand work to a sub-agent/task as already
satisfied by this Gas City lane. Implement only the assigned story, run focused
tests, and preserve actual requirement, story, and acceptance-criterion IDs.

Write the implementation summary at the exact absolute path recorded on the
workflow root as `gc.implementation.summary_path` (fallbacks
`gc.build.implementation_summary_path`, then `gc.var.summary_path`). Do not
write a lane-local substitute. The summary must be Markdown with YAML front
matter valid for `gc.build.implementation-summary.v1`; its first line must be
`---`. Use nested mappings with this top-level shape:

```yaml
---
schema: gc.build.implementation-summary.v1
workflow:
  id: <story-development-workflow-root-id>
  formula: <bmad-story-development-or-bmad-story-development-item>
methodology:
  pack: bmad
  name: bmad-story-development
producer:
  formula: <bmad-story-development-or-bmad-story-development-item>
  stage: implement-story
  attempt: <positive integer>
status: approved
trace: {upstream: [...], coverage: [...]}
---
```

Every `trace.upstream` entry must have `path` and a scheme-qualified `hash`.
Represent the source anchor as `path: beads/<source-anchor-id>` and
`hash: bead:<source-anchor-id>`. Preserve actual source IDs verbatim; never
invent, substitute, or renumber them. Every declared upstream ID must appear
exactly once in `trace.coverage`; when no source declares IDs, omit `ids` and
use `coverage: []`. Every non-`covered` row requires a rationale.

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
- `## Intended Behavior`
- `## Changed Files`
- `## Verification`
- `## Remaining Risks`

Record the first verification command and observed result, changed files,
focused commit hash when applicable, final proof command and observed result,
and remaining risks. Read `gc.build.implementation_control_id` from the
workflow root. Before closing, read the summary path on the workflow root,
current producing child, recorded outer control bead, and actual source anchor;
require all recorded non-empty values to be equal. Record the canonical
absolute path on all four surfaces as `gc.implementation.summary_path`.

Resolve the launcher rig root from workflow root metadata `gc.work_dir`; when
needed use the nearest ancestor containing
`.gc/scripts/checks/build-artifact-valid.sh`. Read the exact current bead ID
from the startup claim output and substitute it literally below; shell
variables from earlier tool calls do not persist. Run:

```bash
GC_BEAD_ID=<exact-claimed-bead-id> <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Fix every validation error in the same summary before setting
`gc.outcome=pass`. On repair attempts, read `gc.attempt_log` from the dependent
validation control bead and repair in place.

Do not invoke provider-native subagents. You are the implementation lane.
