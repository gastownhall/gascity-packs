Verify the completed gstack implementation and write its canonical summary.

Read the workflow root's `gc.build.implementation_convoy_id`,
`gc.input_convoy_id`, and `gc.build.implementation_member_ids`. Require the two
convoy IDs to match and differ from the launch convoy in `gc.var.convoy_id`.
Run `gc convoy status <implementation-convoy-id> --json`; its exact child IDs
must equal the recorded member list, the convoy must be closed, and every
member must have `status=closed`. A closed subset is a failed build.

Read every exact member bead. Require `gc.outcome=pass`, an absolute `work_dir`,
matching `gc.implementation.worktree_path`, a full
`gc.implementation.commit`, and an absolute
`gc.implementation.summary_path` inside that authoritative implementation
worktree. The worktree must be a real git worktree distinct from the launcher
checkout. Under separate-session drain the recorded commit must equal its
`HEAD`; under same-session drain it must be an ancestor retained in the shared
worktree's current `HEAD`. In both modes it must differ from launcher `HEAD`,
and `git status --porcelain --untracked-files=all` must report no staged,
unstaged, or untracked product path. The exact recorded summary artifacts are
the sole evidence-only status exceptions because they bind post-commit proof
to the resulting SHA. Read each item summary and require it to name the exact
source member, worktree, commit, changed files, proof command, and observed
passing result. Do not accept launcher-checkout evidence.

Write the canonical root artifact at the exact path from
`gc.build.implementation_summary_path`. Use Markdown with YAML front matter
valid for `gc.build.implementation-summary.v1`:

```yaml
---
schema: gc.build.implementation-summary.v1
workflow:
  id: <workflow-root-id>
  formula: gstack-build
methodology:
  pack: gstack
  name: gstack-build
producer:
  formula: gstack-build
  stage: summarize-implementation
  attempt: <positive integer>
status: approved
trace:
  upstream:
    - path: <absolute per-item summary path>
      hash: sha256:<summary digest>
      ids: [<actual-source-id>]
  coverage:
    - id: <actual-source-id>
      status: covered
---
```

Preserve actual source and requirement IDs; never invent, substitute, or
renumber them. Every upstream ID must occur exactly once in `trace.coverage`.
Use only allowed coverage statuses and give every non-`covered` entry a
rationale. Include one Markdown table whose `ID` and `Status` pairs exactly
match YAML coverage.

Use these schema-required second-level headings in this exact order:

- `## Summary`
- `## Intended Behavior`
- `## Changed Files`
- `## Verification`
- `## Remaining Risks`

List the exact implementation convoy, member IDs, authoritative worktrees,
full commits, per-item summaries, changed files, proof commands, and observed
results. Each upstream entry must use the current absolute recorded per-item
summary path and `sha256` digest of its current bytes. Use `status: approved`
only when all exact members have passing worktree-bound proof.

Before closing, find the launcher rig root containing
`.gc/scripts/checks/build-artifact-valid.sh`, substitute the exact claimed
bead ID from startup, and run:

```bash
GC_BEAD_ID=<exact-claimed-bead-id> <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Repair every schema or semantic error before setting `gc.outcome=pass`. On a
repair attempt, read `gc.attempt_log` and repair the same canonical summary or
runtime metadata in place. Exhaustion must close with `gc.outcome=fail` and
machine-readable failure metadata.

The runtime control gates this stage with the shipped
`../assets/scripts/checks/gstack-build-state-valid.sh`; that semantic wrapper
runs the shared artifact validator first and then independently verifies the
exact convoy, closure, commit, summary, and worktree state above.

Do not invoke provider-native subagents. This lane verifies and summarizes; it
does not edit product source.
