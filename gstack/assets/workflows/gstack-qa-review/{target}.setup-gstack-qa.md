Prepare the gstack QA context.

Gather staging URLs, local run commands, test commands, acceptance criteria,
and implementation summaries. If a browser surface exists, identify the flows
to exercise. If not, identify the closest command or API workflow.

Build the QA scope from runtime state, not artifact claims. Read
`gc.build.implementation_member_ids` and
`gc.build.implementation_convoy_id` from the workflow root, require `gc convoy
status <implementation-convoy-id> --json` to contain exactly those members and
show all of them closed, then read each member's `work_dir`,
`gc.implementation.worktree_path`, `gc.implementation.commit`, and
`gc.implementation.summary_path`. Require each pair of worktree paths to match
and identify an authoritative implementation worktree distinct from the
launcher checkout. Put this exact member-to-worktree map in the QA context;
missing or inconsistent proof is a blocking QA defect.

Current interaction_mode is {{interaction_mode}} and current review_mode is
{{review_mode}}. Ask for credentials or a staging URL only when the flow cannot
be tested otherwise. In report mode, prepare read-only evidence collection and
do not authorize implementation changes.

Close with `gc.outcome=pass`.

Do not invoke provider-native subagents. Gas City graph lanes are the
delegation mechanism.
