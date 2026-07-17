Run the BMAD story self-check.

Read `gc.build.implementation_source_anchor_id` and
`gc.build.implementation_worktree_path` from the workflow root. Re-read the
source anchor, require its `work_dir` to match that absolute existing git
worktree, set `WORKTREE`, run `cd "$WORKTREE"`, and verify `pwd -P` equals
`$WORKTREE` before reading source, tests, or repository evidence. Never inspect
the launcher checkout or this lane's attempt worktree as a substitute.

Read `gc.build.story_development_artifact_root`,
`gc.build.story_development_context_path`, and
`gc.build.story_self_check_report_path` from the workflow root. Require all
three paths to be absolute, require the context and report paths to be contained
by the recorded story artifact root, and require the context file to exist.
Read that exact context file and require its source anchor, worktree, summary
path, and story/requirement IDs to match workflow-root metadata. Use only that
scope for this check.

Use the installed `bmad-dev-story` skill and quick-dev self-check rules to
verify that every task and acceptance criterion is complete. Record missing work
as required findings.

Write the self-check report to the exact recorded
`gc.build.story_self_check_report_path`. Record that same absolute path on the
current bead and close with `gc.outcome=pass`,
`bmad_story.self_check_report_path=<exact report path>`, and
`bmad_story.self_check_required_findings=<count>`. If the story cannot be
checked because required artifacts or the worktree are missing, close with
`gc.outcome=fail` instead of inventing a result.

Do not invoke provider-native subagents. You are the self-check lane.
