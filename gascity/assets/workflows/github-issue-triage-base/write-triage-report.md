
Use GitHub issue URL {{github_issue_url}} as the source issue for all triage
work in this step.

Load context from bead metadata before investigating:

- Read the current step bead metadata, get `gc.root_bead_id`, then read
  workflow root metadata with `gc bd show <root-bead-id> --json`.
- Required workflow root metadata keys are `gc.github.source_bead_id`,
  `gc.github.repo`, `gc.github.number`, `gc.github.body_hash`,
  `gc.github.snapshot_path`, and `gc.github.triage_dir`.
- If workflow root metadata has `gc.github.reused_current_output=true`, do not
  investigate or rewrite `triage-report.md`. Instead validate the reused
  `gc.github.triage_report_path` with
  `{{pack_root}}/assets/scripts/github_reports.py validate-triage --repo
  <gc.github.repo> --issue-number <gc.github.number> --body-hash
  <gc.github.body_hash>`, verify it lives under `gc.github.triage_dir`,
  refresh `gc.github.triage_verdict`, `gc.github.triage_priority`, and
  `gc.github.triage_recommended_next_action` from the report front matter,
  close this step with `gc.outcome=pass`, and leave the reused artifacts
  untouched. This is the no-op path that makes current body-hash reuse
  effective even though the formula graph still schedules this step.
- Read `gc.github.snapshot_path` for the issue title, body, labels, author,
  timestamps, and canonical URL. Do not refetch the issue unless the snapshot
  file is missing or invalid.
- Write `triage-report.md` under `gc.github.triage_dir`.

Behavior customization:

- Optional rubric/prompt override path: {{triage_rubric_path}}.
- If this value is non-empty, read that Markdown file before deciding the
  verdict and writing the analysis body. Treat it as a user-supplied rubric or
  skeleton for report behavior, not the metadata protocol.
- The rubric may customize investigation strategy, project-specific label or
  priority semantics, issue-kind policy, public explanation style, and the
  human-readable report body skeleton.
- The rubric must not override workflow metadata handoff, artifact paths,
  report schema `gc.github-issue-triage-report.v1`, validator rules, security
  or p0 human-gate behavior, comment marker requirements, or the ban on
  implementation convoys, commits, pushes, PRs, and source-branch mutation.
  If the rubric conflicts with those base protocol rules, follow this formula
  and note the conflict in the report.
- If the path is empty, use the base rubric below.

Investigate the issue and optional repro evidence. Write the report with schema
`gc.github-issue-triage-report.v1`, then validate it with
`{{pack_root}}/assets/scripts/github_reports.py validate-triage --repo <gc.github.repo> --issue-number <gc.github.number> --body-hash <gc.github.body_hash>`.

The YAML front matter is only the machine contract. Below it, write a useful
human-readable analysis body with at least:
- `## Summary`: what you found and why the verdict follows.
- `## Evidence`: concrete source/test/runtime evidence, including commands,
  files, or artifacts checked.
- `## Recommendation`: the next action and any residual risk.

Allowed verdicts are `reproduced`, `not_reproduced`, `needs_info`, `not_a_bug`,
`duplicate`, and `security_sensitive`. Allowed next actions are bound to the
verdict by the validator. Reproduction work may write logs, repro scripts, and
patch evidence under the triage artifact directory only.

After validation, update the workflow root metadata with the report result:
`gc bd update <root-bead-id> --set-metadata gc.github.triage_report_path=<absolute triage-report.md path> --set-metadata gc.github.triage_verdict=<verdict> --set-metadata gc.github.triage_priority=<priority> --set-metadata gc.github.triage_recommended_next_action=<recommended_next_action>`.
