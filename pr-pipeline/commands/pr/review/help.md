Self-review an outgoing PR against an 11-category scorecard before
requesting external review. Catches structural and correctness defects
that a careful maintainer review would flag.

This dispatches a coding agent to a rig with the `mol-pr-review` formula.
The agent fetches the PR diff, scores findings across 11 categories,
pre-flags 7 recurring fixup themes, and writes a scorecard report to
`.gc/pr-pipeline/reviews/pr-<N>.md`. **No fixes are applied** — apply
fixes by re-iterating the development loop, not by extending this formula.

Scope: `mol-pr-review` reviews **outgoing** PRs (your own PR before
submitting it). Reviewing **incoming** PRs (someone else's PR; review +
merge) is a separate, maintainer-side concern, not covered here.

Usage:
  gc <binding> pr review <pr-number-or-url> [flags]

Arguments:
  <pr>                PR number (in current repo) or GitHub PR URL.

Flags:
  --rig <name>        Rig to review inside (defaults to $GC_RIG).
  --agent <name>      Worker agent name (default: "polecat").

Examples:
  gc <binding> pr review 1234 --rig api-server
  gc <binding> pr review https://github.com/owner/repo/pull/1234

Direct sling (skip this command):
  gc sling api-server/polecat mol-pr-review --formula --var pr=1234

Output:
  Report at <repo-root>/.gc/pr-pipeline/reviews/pr-<N>.md
  Root-bead notes record `verdict:` (block | request_changes | approve).

Decision policy (mechanical):
  Unresolved blocker in cat 1-4   → verdict block
  Unresolved blocker in cat 5-8   → verdict request_changes
  Major in cat 1-8 unmitigated    → verdict request_changes
  Only minors / nits              → verdict approve
