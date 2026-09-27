Apply required BMAD story findings.

Make the smallest implementation and test changes needed to resolve required self-check or acceptance-audit findings. If no required findings exist, record a no-op fix result and preserve the review artifact path.

Read the BMAD story self-check and acceptance-audit reports from the current
attempt. Write the fix summary under
`{{artifact_root}}/bmad-story-development/`.

If there are no required findings, perform a no-op pass and close with
`gc.outcome=pass`, `bmad_story.verdict=done`, and
`bmad_story.report_path=<fix summary path>`. Also set
`code_review.verdict=done` and `code_review.report_path=<fix summary path>` so
the inherited implementation-review check can approve the BMAD story loop.

Make any code or test changes in the same source-anchor worktree the
implement-story step committed in (`work_dir` on the source anchor), and commit
them there as a focused commit (`git add` the changed files and `git commit`)
so `close-source-anchor` verifies the fixed code, not only the first attempt.

If required findings were present and you changed and committed code or tests
to address them, close with `gc.outcome=pass`, `bmad_story.verdict=iterate`, and
`bmad_story.report_path=<fix summary path>`. Also set
`code_review.verdict=iterate` and `code_review.report_path=<fix summary path>`
so the Gas City loop reruns the BMAD self-check and acceptance audit on the
changed worktree. If required findings remain unresolved, close with
`gc.outcome=fail`.

Do not invoke provider-native subagents. This Gas City lane owns the story-fix pass.
