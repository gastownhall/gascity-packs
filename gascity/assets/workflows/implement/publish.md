
If push {{push}} or open_pr {{open_pr}} are explicit opt-ins, publish only
after the direct implementation summary has completed successfully. Resolve the
publish report from summary_path {{summary_path}} when set; otherwise read the
`gc.implementation.summary_path` value recorded by the summarize step in
workflow root metadata. Fail closed if no absolute summary report path is
available.

Direct implement does not run gap-analysis or review loops. Treat this as an
explicit caller authorization to publish the direct implementation result, and
use the same protected-branch, lease-safe push, sanitized PR title/body, and
collision checks as the pack publish helper. If neither push nor open_pr is an
explicit opt-in, close with `gc.outcome=pass` without mutating remotes.

Sanitized means: the PR title and body describe the change in terms a
reviewer with no access to gc's internal tracking would understand. Before
opening the PR, strip or rewrite anything that only makes sense inside gc —
bead/convoy/epic IDs (e.g. `tlp-xxxxx`, `ga-xxx`), internal requirement labels
like `REQ-001`/`REQ-002`, workflow/formula names, and coverage tables copied
verbatim from the implementation-summary artifact. If the target repo
publishes its own PR conventions (e.g. a `github-conventions.md` or
`CONTRIBUTING.md` under its docs), follow those over this default. When in
doubt, write the body as if explaining the change to someone outside gc
entirely.
