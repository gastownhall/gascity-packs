This is the `build-from-convoy-base` handoff into the inherited review suffix.

Read the drain result for the implementation convoy and record the
implementation evidence path as `gc.implementation.summary_path` or
`gc.build.implementation_summary_path` on the workflow root. Then validate the
inputs required by `build-from-review-base`, including
`review_repair_policy: {{review_repair_policy}}`.

Write `<artifact_root>/review-context.md` with an `## Implementation Worktrees`
section (source anchor id, absolute implementation worktree from the source
anchor's `work_dir`, base revision and diff range `<base>..HEAD`, changed files,
proof commands from the implementation summary; append artifact excerpts with
`cat`, never literal `$(...)`), record `gc.build.code_review_context_path` and
`gc.build.review_repair_policy` on the workflow root, and close with
`gc.outcome=fail` and a machine-readable reason if no implementation worktree
can be resolved.

Do not review or fix code in this step. Close only after the review suffix can
consume the implementation evidence without inspecting drain internals.
