Synthesize the Jev-gated review.

Read the reports of the lanes that ran in this iteration (some lanes may have
been cleared by the Jev gate; their beads do not exist). Deduplicate findings,
preserve the source lane for each, and classify each item as required fix,
missing evidence, or residual risk. Smells Jev confirmed are required fixes:
{forwarded_smells}.

Also read `gc.build.code_review_context_path` from the workflow root bead. When
you carry a finding forward, include the source anchor and implementation
worktree from the context's `## Implementation Worktrees` section. Resolve
relative filenames against the implementation worktree, never the launcher
checkout.

Contract: `gc.work_dir` is the launcher rig root, not the implementation worktree.

Write one short synthesis under the build artifact root. Close with
`gc.outcome=pass`, `code_review.synthesis_path=<synthesis path>`, and
`code_review.output_path=<synthesis path>`.

Do not invoke provider-native subagents.
