
Resolved GitHub issue URL: {{github_issue_url}}
Resolved artifact root override: {{artifact_root}} (empty means use the rig artifact root)
Resolved mode alias: {{mode}}
Resolved interaction mode: {{interaction_mode}} (empty means normalize from the mode alias)
Resolved review mode: {{review_mode}}
Resolved PR mode: {{pr_mode}}
Resolved drain policy: {{drain_policy}}

Normalize the interaction mode before any other work. `mode` is only a
backward-compatible alias: the effective interaction mode is
`interaction_mode` when non-empty, otherwise `mode`. The effective value must
be `interactive`, `autonomous`, or `headless`; `review_mode` must be `report`,
`agent`, or `interactive`; `drain_policy` must be `separate` or
`same-session`. Read the current step bead with `gc bd show <current-step-bead-id>
--json`, take `gc.root_bead_id` (hard-fail if missing), and record the
normalized value on the workflow root with
`gc bd update <root-bead-id> --set-metadata gc.var.interaction_mode=<effective interaction mode>`.
Downstream steps read `gc.var.interaction_mode`, never the raw alias.

Methodology selector compatibility gate. For each selected formula —
planning_formula {{planning_formula}}, decomposition_formula
{{decomposition_formula}}, implementation_formula {{implementation_formula}},
implementation_item_formula {{implementation_item_formula}},
code_review_formula {{code_review_formula}}, and review_fix_formula
{{review_fix_formula}} — read its declared compatibility metadata with
`gc formula show <formula-name> --json` and inspect `[metadata.gc.methodology]`
(`allowed_drain_policies`, `implementation_strategy`, `interaction_modes`,
`review_modes`). Enforce, for every formula that declares the metadata:

- the effective interaction mode is listed in `interaction_modes`;
- the requested `review_mode` is listed in `review_modes` for the selected
  code-review and review-fix formulas;
- the implementation formula supports the requested drain policy:
  `implementation_strategy = "drain"` requires {{drain_policy}} to be listed in
  `allowed_drain_policies`, while `implementation_strategy = "convoy-step"` may
  declare no drain policies and ignores `drain_policy`;
- declared metadata uses only the allowed vocabulary above; unknown values fail
  this gate.

A selected formula with no `[metadata.gc.methodology]` declares no mode
constraint and passes this gate. If any requested value is outside the
vocabulary or unsupported by a selected formula, stop blocked before snapshot,
triage, or planning work: record `gc.github.methodology_compat=blocked` and a
machine-readable `gc.blocked_reason` (for example
`unsupported-drain-policy:same-session-for:{{implementation_formula}}`) on the
workflow root, then close this step with `gc.outcome=fail` and
`gc.failure_class=methodology_incompatible`. In `headless` interaction mode,
never ask questions; missing required input is the same blocked outcome.
Otherwise record `gc.github.methodology_compat=ok` on the workflow root.

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
reject shorthand inputs, and refresh the canonical GitHub source bead using
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

Do not use title, label, assignee, or state changes to invalidate downstream
fix reuse; `gc.github.body_hash` is the issue content key.
