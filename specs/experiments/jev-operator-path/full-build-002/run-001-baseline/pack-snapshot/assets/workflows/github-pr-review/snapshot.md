
Resolved GitHub PR URL: {{github_pr_url}}
Resolved artifact root override: {{artifact_root}} (empty means use the rig artifact root)
Resolved context path: {{context_path}} (empty means no extra context bundle)
Resolved code review formula: {{code_review_formula}}
Resolved interaction mode: {{interaction_mode}}
Resolved review mode: {{review_mode}}
Resolved post mode: {{post_mode}}

Methodology compatibility gate. Validate mode inputs before snapshot work:
`interaction_mode` {{interaction_mode}} must be `interactive`, `autonomous`,
or `headless`; `review_mode` {{review_mode}} must be `report`, `agent`, or
`interactive`. Read the selected code-review formula's compatibility metadata
with `gc formula show {{code_review_formula}} --json` and inspect
`[metadata.gc.methodology]`. When the formula declares that metadata, the
requested review mode must be listed in `review_modes` and the requested
interaction mode must be listed in `interaction_modes`; declared metadata must
use only the allowed vocabulary. A formula with no declared metadata passes
this gate. In `headless` interaction mode, `post_mode` must not be
`human_gate`: headless runs never wait on a human comment gate. If any check
fails, stop blocked before snapshot work: record
`gc.github.methodology_compat=blocked` and a machine-readable
`gc.blocked_reason` (for example
`unsupported-review-mode:{{review_mode}}-for:{{code_review_formula}}` or
`headless-requires-post-mode:auto`) on the workflow root, then close this step
with `gc.outcome=fail` and `gc.failure_class=methodology_incompatible`.
Otherwise record `gc.github.methodology_compat=ok` on the workflow root.

Artifact root semantics:
- Resolve the durable artifact root with
  `{{pack_root}}/assets/scripts/artifacts.py root --override "{{artifact_root}}"`.
- Paths shown with a leading slash, such as
  `/github/pulls/<owner>/<repo>/<number>/source.json`, are
  artifact-root-relative, not filesystem-root absolute.
- Resolve concrete files with
  `{{pack_root}}/assets/scripts/artifacts.py path --override "{{artifact_root}}" --relative "/github/pulls/<owner>/<repo>/<number>/source.json" --mkdir-parents`.
- Store absolute resolved artifact paths in bead metadata. Do not infer source
  identity, workflow identity, readiness, or routing from artifact paths.

Validate the PR URL with
`{{pack_root}}/assets/scripts/github_api.py parse-url "{{github_pr_url}}" --kind pull`,
reject shorthand inputs, then fetch the current PR source snapshot with
`{{pack_root}}/assets/scripts/github_api.py pr-snapshot "{{github_pr_url}}"`.

Write the returned snapshot JSON to
artifact-root-relative path `/github/pulls/<owner>/<repo>/<number>/source.json`.
Then create or refresh the canonical GitHub source bead using this v0 contract:

- Source beads are non-runnable index/cache beads. Do not route the source bead,
  assign it, depend on it, or use it as a readiness gate.
- Lookup uses object identity only:
  `gc bd list --metadata-field gc.kind=github_source --metadata-field gc.github.kind=pull --metadata-field gc.github.repo=<owner>/<repo> --metadata-field gc.github.number=<number> --status open,in_progress,closed --limit 1 --json`.
- Write `source-metadata.json` with flat string metadata:
  `gc.kind=github_source`, `gc.github.kind=pull`,
  `gc.github.repo=<owner>/<repo>`, `gc.github.number=<number>`,
  `gc.github.url=<canonical_url>`, `gc.github.title=<title>`,
  `gc.github.state=<state>`, `gc.github.author=<author>`,
  `gc.github.body_hash=<body_hash>`,
  `gc.github.head_sha=<head_sha>`, `gc.github.head_ref=<head_ref>`,
  `gc.github.head_repo=<head_repo>`, `gc.github.base_ref=<base_ref>`,
  `gc.github.base_repo=<base_repo>`,
  `gc.github.snapshot_path=<absolute source.json path>`,
  `gc.github.updated_at=<updated_at>`.
- If no bead exists, create it with
  `gc bd create "GitHub PR source: <owner>/<repo>#<number>" --type task --labels gc.github-source,gc.github-pr --external-ref <canonical_url> --metadata @source-metadata.json`.
- If a bead exists, refresh it with
  `gc bd update <source-bead-id> --external-ref <canonical_url> --metadata @source-metadata.json`.

Then stamp workflow root metadata as the context handoff index for downstream
steps. Do not write a separate PR-review context file; bead metadata is the
small stable index, and artifact files hold large payloads.

- Read the current step bead with `gc bd show <current-step-bead-id> --json` and
  take `gc.root_bead_id`; hard-fail if it is missing.
- Resolve the current head-SHA review directory with
  `{{pack_root}}/assets/scripts/artifacts.py path --override "{{artifact_root}}" --relative "/github/pulls/<owner>/<repo>/<number>/reviews/<head-sha>/" --mkdir-parents --directory`.
- Update the workflow root metadata with:
  `gc bd update <root-bead-id> --set-metadata gc.github.source_bead_id=<source-bead-id> --set-metadata gc.github.kind=pull --set-metadata gc.github.repo=<owner>/<repo> --set-metadata gc.github.number=<number> --set-metadata gc.github.url=<canonical_url> --set-metadata gc.github.head_sha=<head_sha> --set-metadata gc.github.snapshot_path=<absolute source.json path> --set-metadata gc.github.review_dir=<absolute review directory> --set-metadata gc.github.artifact_root=<absolute artifact root> --set-metadata gc.github.context_path={{context_path}} --set-metadata gc.github.post_mode={{post_mode}} --set-metadata gc.github.reused_current_output=false`.

Only `gc.github.head_sha` controls head-SHA-keyed PR review reuse.
