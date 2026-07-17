Audit BMAD story acceptance.

Read `gc.build.implementation_source_anchor_id` and
`gc.build.implementation_worktree_path` from the workflow root. Re-read the
source anchor, require its `work_dir` to match that absolute existing git
worktree, set `WORKTREE`, run `cd "$WORKTREE"`, and verify `pwd -P` equals
`$WORKTREE` before reading source, tests, or repository evidence. Never inspect
the launcher checkout or this lane's attempt worktree as a substitute.

Read `gc.build.story_development_artifact_root`,
`gc.build.story_development_context_path`, and
`gc.build.acceptance_audit_report_path` from the workflow root. Require all
three paths to be absolute, require the context and report paths to be contained
by the recorded story artifact root, and require the context file to exist.
Read that exact context file and require its source anchor, worktree, summary
path, and story/requirement IDs to match workflow-root metadata. Use only that
scope for this audit.

Compare the implementation against the PRD, architecture, epics/stories, and
Given/When/Then acceptance criteria from the exact recorded context. Check test
evidence and flag missing, extra, or misunderstood behavior.

Write the acceptance-audit report to the exact recorded
`gc.build.acceptance_audit_report_path`. Record that same absolute path on the
current bead and close with `gc.outcome=pass`,
`bmad_story.acceptance_audit_report_path=<exact report path>`, and
`bmad_story.acceptance_required_findings=<count>`. If the story cannot be
audited because required artifacts or the worktree are missing, close with
`gc.outcome=fail` instead of inventing a result.

Do not invoke provider-native subagents. You are the acceptance audit lane.
