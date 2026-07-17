Prepare the BMAD story-development context.

Read the current step's `gc.root_bead_id` and inspect that inner workflow root.
For `bmad-story-development`, resolve the source anchor from the root's
`gc.input_convoy_id`; unwrap a `gc.synthetic_kind=drain-unit-convoy` by using
its `gc.drain_member_id`.

For `bmad-story-development-item`, read `gc.input_convoy_id`,
`gc.drain_member_id`, and `gc.drain_item_index` from the inner workflow root.
Require the root member and index to be non-empty. Read the reserved input
convoy named by `gc.input_convoy_id`; if it also records a member or index,
require exact equality with the inner root values. Use only the inner root's
`gc.drain_member_id` as the source anchor. Never infer the source anchor from a
dependency bead or use the reserved or synthetic convoy as the anchor.

Resolve the current iteration root before locating the outer `implement` or
`implement-item` validation control. Read the claimed child's `gc.attempt` and
`gc.scope_ref`. Treat `gc.scope_ref` as a bead ID when it resolves directly;
otherwise select the unique bead under the same workflow root whose
`gc.step_ref` equals that scope reference, whose `gc.attempt` equals the child
attempt, and whose `gc.step_id` identifies the expected outer step. Require
that bead to be the current iteration root, not a body child or control bead.

Read `gc.control_for` from that iteration root. On runtime retries it is the
durable control's bead ID, so resolve that exact bead. On the compile-time first
attempt it may instead be the control identity; in that case select the unique
same-root validation control whose bead ID, `gc.step_ref`, or `gc.step_id`
equals `gc.control_for` and whose `gc.step_id` is the expected `implement` or
`implement-item`. Require the selected bead to have the validation-control kind
and the same workflow root. The durable control must not carry `gc.attempt`;
never filter the control itself by attempt. Reject an absent or ambiguous
lineage match. Record its bead ID on the workflow root and current producing
child as `gc.build.implementation_control_id`.

Read `work_dir` from the source anchor and require an absolute, existing git
worktree distinct from the launcher checkout. Set `WORKTREE` to that path, run
`cd "$WORKTREE"`, and verify `pwd -P` equals `$WORKTREE` before reading source
or repository evidence. Record the canonical path on the workflow root as
`gc.build.implementation_worktree_path` and record the source anchor as
`gc.build.implementation_source_anchor_id`.

Resolve the launcher rig root from workflow root metadata `gc.work_dir`,
walking to the nearest ancestor containing
`.gc/scripts/checks/build-artifact-valid.sh` when the metadata names an attempt
worktree. Resolve the artifact root from workflow root metadata
`gc.var.artifact_root` (fallback `gc.build.artifact_root`, then rendered
`{{artifact_root}}`). The artifact root belongs to the launcher workflow; never
interpret a relative artifact path against the implementation worktree.
Resolve a relative artifact root against the launcher rig root and normalize it
to an absolute path.

Create one per-source-anchor directory at
`<artifact-root>/bmad-story-development/<source-anchor-id>`, require it to be
contained by the resolved artifact root, and record it on the workflow root as
`gc.build.story_development_artifact_root`. Derive these absolute paths from
that directory and record each on the workflow root before child lanes run:

- `gc.build.story_development_context_path=<story-artifact-root>/context.md`
- `gc.build.story_self_check_report_path=<story-artifact-root>/story-self-check.md`
- `gc.build.acceptance_audit_report_path=<story-artifact-root>/acceptance-audit.md`
- `gc.build.story_fix_summary_path=<story-artifact-root>/apply-summary.md`

Select the canonical summary path from workflow root metadata
`gc.implementation.summary_path` (fallbacks
`gc.build.implementation_summary_path`, then `gc.var.summary_path`). Resolve
every selected non-empty summary path to an absolute path against `WORKTREE`
when it is relative, and require the result to be contained by `WORKTREE`. If
all keys are empty, derive `<WORKTREE>/implementation-summary.md`. The story
artifact root remains the home for context and review reports, but it is not an
authoritative implementation worktree and must not contain the per-item
implementation summary. On retries, read any existing
summary path from the inner workflow root, current producing child, recorded
implementation control bead, and actual source anchor; normalize relative
values against `WORKTREE` and require exact equality for every
non-empty value.

Always record the selected absolute path as `gc.implementation.summary_path`
on the inner workflow root, current producing child, recorded outer control
bead, and actual source anchor before any producer runs. These are one artifact
identity, not fallback locations.

Resolve the BMAD PRD, architecture, epics/stories output, implementation convoy,
current story bead, sprint/status context, and verification expectations. Write
a compact context file at the exact recorded
`gc.build.story_development_context_path` containing the canonical source
anchor, worktree, summary path, requirements, architecture, decomposition, and
story scope. Preserve actual requirement and story IDs verbatim.

Close with `gc.outcome=pass` only after the story artifact directory and context
file exist and every recorded path is absolute and resolves as described.

Do not invoke provider-native subagents or upstream BMAD runtime commands. This
graph stage converts BMAD's sub-agent/task handoff into Gas City lanes.
