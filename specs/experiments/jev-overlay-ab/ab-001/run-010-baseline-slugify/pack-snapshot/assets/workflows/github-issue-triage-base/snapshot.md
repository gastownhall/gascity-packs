
Resolved GitHub issue URL: {{github_issue_url}}
Resolved artifact root override: {{artifact_root}} (empty means use the rig artifact root)
Resolved post mode: {{post_mode}}

Artifact root semantics:
- Resolve the durable artifact root with
  `{{pack_root}}/assets/scripts/artifacts.py root --override "{{artifact_root}}"`.
- Paths shown with a leading slash, such as
  `/github/issues/<owner>/<repo>/<number>/source.json`, are
  artifact-root-relative, not filesystem-root absolute.
- Resolve concrete files with
  `{{pack_root}}/assets/scripts/artifacts.py path --override "{{artifact_root}}" --relative "/github/issues/<owner>/<repo>/<number>/source.json" --mkdir-parents`.
- Store absolute resolved artifact paths in bead metadata. Do not infer source
  identity, workflow identity, readiness, or routing from artifact paths.

Validate the issue URL with
`{{pack_root}}/assets/scripts/github_api.py parse-url "{{github_issue_url}}" --kind issue`,
reject shorthand inputs, then fetch the current source snapshot with
`{{pack_root}}/assets/scripts/github_api.py issue-snapshot "{{github_issue_url}}"`.

Write the returned snapshot JSON to
artifact-root-relative path `/github/issues/<owner>/<repo>/<number>/source.json`.
Then create or refresh the canonical GitHub source bead using this v0 contract:

- Source beads are non-runnable index/cache beads. Do not route the source bead,
  assign it, depend on it, or use it as a readiness gate.
- Lookup uses object identity only:
  `gc bd list --metadata-field gc.kind=github_source --metadata-field gc.github.kind=issue --metadata-field gc.github.repo=<owner>/<repo> --metadata-field gc.github.number=<number> --status open,in_progress,closed --limit 1 --json`.
- Write `source-metadata.json` with flat string metadata:
  `gc.kind=github_source`, `gc.github.kind=issue`,
  `gc.github.repo=<owner>/<repo>`, `gc.github.number=<number>`,
  `gc.github.url=<canonical_url>`, `gc.github.title=<title>`,
  `gc.github.state=<state>`, `gc.github.author=<author>`,
  `gc.github.labels=<comma-separated labels>`,
  `gc.github.body_hash=<body_hash>`,
  `gc.github.snapshot_path=<absolute source.json path>`,
  `gc.github.updated_at=<updated_at>`.
- If no bead exists, create it with
  `gc bd create "GitHub issue source: <owner>/<repo>#<number>" --type task --labels gc.github-source,gc.github-issue --external-ref <canonical_url> --metadata @source-metadata.json`.
- If a bead exists, refresh it with
  `gc bd update <source-bead-id> --external-ref <canonical_url> --metadata @source-metadata.json`.

Then stamp workflow root metadata as the context handoff index for downstream
steps. Do not write a separate triage context file; bead metadata is the small
stable index, and artifact files hold large payloads.

- Read the current step bead with `gc bd show <current-step-bead-id> --json` and
  take `gc.root_bead_id`; hard-fail if it is missing.
- Resolve the current triage directory with
  `{{pack_root}}/assets/scripts/artifacts.py path --override "{{artifact_root}}" --relative "/github/issues/<owner>/<repo>/<number>/triage/<body-hash>/" --directory --mkdir-parents`.
- Update the workflow root metadata with:
  `gc bd update <root-bead-id> --set-metadata gc.github.source_bead_id=<source-bead-id> --set-metadata gc.github.kind=issue --set-metadata gc.github.repo=<owner>/<repo> --set-metadata gc.github.number=<number> --set-metadata gc.github.url=<canonical_url> --set-metadata gc.github.body_hash=<body_hash> --set-metadata gc.github.snapshot_path=<absolute source.json path> --set-metadata gc.github.triage_dir=<absolute triage directory> --set-metadata gc.github.artifact_root=<absolute artifact root> --set-metadata gc.github.post_mode={{post_mode}} --set-metadata gc.github.reused_current_output=false`.

Do not use title, label, assignee, or state changes to invalidate triage; only
`gc.github.body_hash` controls body-hash-keyed triage reuse.
