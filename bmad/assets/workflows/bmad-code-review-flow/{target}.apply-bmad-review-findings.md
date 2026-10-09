Apply required BMAD code-review findings.

Read the synthesized BMAD review report and resolve required findings in this
single lane. Preserve traceability to the review lane, story id, acceptance
criteria, file anchors, and severity.

Read the synthesized report from `gc.build.code_review_report_path`. Write the
review-fix summary to `gc.build.review_fix_summary_path`, which should be
`{{artifact_root}}/code-review/apply-summary.md`.

Use implementation target {{implementation_target}} for any code changes.
Close this lane only after the implementation summary and BMAD review artifact
record changed files, tests run, resolved findings, and blockers. If there are
no required fixes, record a no-op review-fix artifact instead of editing code.

If the synthesized report approves the implementation with no required fixes,
perform a no-op pass, update workflow root metadata with
`gc.build.code_review_status=approved`, and close with
`code_review.verdict=done`. If required fixes remain after processing, update
workflow root metadata with `gc.build.code_review_status=draft` and close with
`code_review.verdict=iterate`.

Always close with `gc.outcome=pass`,
`code_review.report_path=<review fix summary path>`, and
`code_review.output_path=<review fix summary path>`.

Keep edited build artifacts schema-valid. Stage checks and the build gate's final artifact check validate these
Markdown build artifacts, so any edit you make to one must leave it valid:

- The implementation summary at workflow root metadata `gc.build.implementation_summary_path`, schema `gc.build.implementation-summary.v1`:
  front-matter `status` must be one of `draft`, `approved`, `blocked`, or `superseded`.
- The synthesized review report at workflow root metadata `gc.build.code_review_report_path`, schema `gc.build.review.v1`:
  front-matter `status` must be one of `draft`, `questions`, `approved`, `changes_required`, `blocked`, or `superseded`.

When you edit one of them:

- Edit it in place and preserve its YAML front matter: keep `schema`,
  `workflow`, `methodology`, `producer`, and `trace` intact, and keep
  `trace.coverage` and the Markdown `ID`/`Status` coverage table in sync.
- Use only the allowed `status` values listed above. Do not invent statuses
  such as `reviewed`; record review progress in the apply summary and bead
  metadata, not in the artifact's front matter.
- Before closing with `gc.outcome=pass`, from `$GC_RIG_ROOT`, re-run the
  validator on every build artifact you edited and fix every reported error:
  `python3 .gc/scripts/validate_build_artifact.py --schema gc.build.implementation-summary.v1 --path "<implementation summary path>"`.
  `python3 .gc/scripts/validate_build_artifact.py --schema gc.build.review.v1 --path "<review report path>"`.
- On a repeated attempt (`gc.attempt` greater than 1), first read the validator
  errors from `gc.attempt_log` on the loop control bead and repair the
  artifact in place.

Do not invoke provider-native subagents. This graph lane is the delegation
mechanism.
