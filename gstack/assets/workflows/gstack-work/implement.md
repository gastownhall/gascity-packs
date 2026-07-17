Implement the assigned gstack work bead.

Gas City owns the worktree, bead, and convoy plumbing. Resolve the source anchor
before reading or editing source. Read the claimed step bead's
`gc.root_bead_id`, then read that gstack-work workflow root bead and its
`gc.input_convoy_id`. If the input convoy has
`gc.synthetic_kind=drain-unit-convoy`, use its `gc.drain_member_id` as the
source anchor; otherwise use the input convoy ID. Never use a dependency or the
synthetic convoy itself as the source anchor.

Read `work_dir` from the source anchor and require it to be an absolute,
existing git worktree distinct from the launcher checkout. Set `WORKTREE` to
that path, run `cd "$WORKTREE"`, and verify `pwd -P` equals `$WORKTREE` before
any source read, source edit, test, hash, commit, or proof command. `gc.work_dir`
on the workflow root bead is the launcher rig root used for validation; it is
not the implementation worktree.

Read the assigned implementation bead, approved plan, and any context bundle
only after entering the authoritative worktree. Use the gstack discipline: ship
the narrowest complete slice, test it, review your own diff, and record proof.

Write the implementation summary as Markdown with YAML front matter valid for
`gc.build.implementation-summary.v1`, not as a freeform note or JSON. Read its
path from workflow root metadata `gc.implementation.summary_path` (fallbacks
`gc.build.implementation_summary_path`, then `gc.var.summary_path`). If all are
blank, derive an absolute per-item path for this source anchor and record it on
the workflow root bead as `gc.implementation.summary_path` before closing.

Use nested mappings with this top-level shape:

```yaml
---
schema: gc.build.implementation-summary.v1
workflow:
  id: <gstack-work-workflow-root-id>
  formula: gstack-work
methodology:
  pack: gstack
  name: gstack-work
producer:
  formula: gstack-work
  stage: implement
  attempt: <positive integer>
status: approved
trace: {upstream: [...], coverage: [...]}
---
```

The artifact's first line must be `---`. Every `trace.upstream` entry must have
`path` and a scheme-qualified `hash`. Represent the source anchor as
`path: beads/<source-anchor-id>` and `hash: bead:<source-anchor-id>`. Preserve
actual source IDs verbatim; never invent, substitute, or renumber them. Every
upstream ID must appear exactly once in `trace.coverage`; when the source
declares no IDs, omit `ids` and use `coverage: []`. Every non-`covered` entry
must have a rationale. Include one Markdown table whose `ID` and `Status` pairs
exactly match the YAML coverage:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Only include the example data row when coverage is non-empty, and replace the
placeholder with an actual ID. When coverage is empty, do not add a data row;
omit the table or use only its header and separator.

Use these schema-required second-level headings in this exact order:

- `## Summary`
- `## Intended Behavior`
- `## Changed Files`
- `## Verification`
- `## Remaining Risks`

Include intended behavior, the first verification command and observed result,
changed files, the final proof command and observed result, remaining risks,
and any release consideration.

Bind the proof to the source anchor bead and authoritative implementation
worktree, not to the launcher checkout. After the focused commit, read the full
commit SHA with `git rev-parse HEAD` from `$WORKTREE`. The summary must contain
the exact `beads/<source-anchor-id>` reference, canonical absolute worktree
path, full commit SHA, changed files from that commit, and the observed passing
result of the final proof command run from that worktree. Then persist all
three proof values on the source anchor bead itself:

```bash
gc bd update <source-anchor-id> \
  --set-metadata 'gc.implementation.worktree_path=<canonical absolute worktree>' \
  --set-metadata 'gc.implementation.commit=<full commit SHA>' \
  --set-metadata 'gc.implementation.summary_path=<absolute summary path inside that worktree>'
```

Read the source anchor bead back and require `work_dir` and
`gc.implementation.worktree_path` to resolve to the same worktree, the recorded
commit to equal that worktree's `HEAD`, and the recorded summary to exist
inside that worktree. Do not record or accept launcher-checkout proof.

From `$WORKTREE`, run `git status --porcelain --untracked-files=all` after
writing the post-commit summary. Each recorded per-item summary is the only
permitted uncommitted path for its member; other already-recorded member
summaries in the same shared worktree are also evidence-only exceptions. Fail
instead of closing if status reports any other staged, unstaged, or untracked
path. An untracked product file is incomplete implementation, not evidence.

Before closing, return only as needed to the launcher rig root resolved from
the workflow root bead's `gc.work_dir` and run the canonical check without
using the launcher checkout for source operations. If that root does not contain
the validator, use the nearest ancestor containing
`.gc/scripts/checks/build-artifact-valid.sh`. Read the exact current bead ID
from the startup claim output and substitute it literally below; shell variables
from earlier tool calls do not persist:

```bash
GC_BEAD_ID=<exact-claimed-bead-id> <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Fix every validation error in the recorded summary before setting
`gc.outcome=pass`.

Close with `gc.outcome=pass` only after the work is implemented and verified.

Do not invoke provider-native subagents. You are the implementation lane.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
