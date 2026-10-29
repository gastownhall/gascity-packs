
Read the current step bead metadata, get `gc.root_bead_id`, then read
workflow root metadata with `gc bd show <root-bead-id> --json`. Use
`gc.github.repo`, `gc.github.number`, `gc.github.body_hash`,
`gc.github.snapshot_path`, and `gc.github.triage_dir` as the context index.
If any required key is missing, hard-fail and report that the snapshot handoff
metadata is incomplete.

If a validated `triage-report.md` and current comment metadata already exist
for the same repo, issue number, and body hash, return that run after refreshing
source metadata and stamping `gc.github.reused_current_output=true`.

When reusing, set at least `gc.github.triage_report_path=<absolute
triage-report.md path>`, `gc.github.comment_path=<absolute comment.md path>`,
`gc.github.triage_verdict=<verdict>`, `gc.github.triage_priority=<priority>`,
and `gc.github.triage_recommended_next_action=<recommended_next_action>` on
the workflow root. Validate the report with
`{{pack_root}}/assets/scripts/github_reports.py validate-triage --repo
<gc.github.repo> --issue-number <gc.github.number> --body-hash
<gc.github.body_hash>` before stamping metadata. If the stored comment was
deleted, create a replacement from the existing rendered comment and update
workflow root metadata.

If no current reusable artifacts exist, stamp
`gc.github.reused_current_output=false` and close this step with
`gc.outcome=pass`; do not leave a stale true reuse flag for downstream steps.
