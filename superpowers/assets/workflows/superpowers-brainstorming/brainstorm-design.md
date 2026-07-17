Use the installed Superpowers brainstorming guidance as methodology reference.
Treat it as reference material, not as an interactive workflow. This lane
produces a design candidate; the downstream `confirm-design-approval` lane owns
approval and every human interaction.

First read the exact workflow root id printed by the successful claim. Query
that root with `gc bd show <claimed-root-id> --json` and normalize the response
with this jq selector before reading metadata:

```jq
(if type == "array" then .[0] else . end) | .metadata
```

Read `gc.var.interaction_mode`, `gc.var.brainstorming_approval_mode`,
`gc.build.design_path`, `gc.build.design_gate_artifact_path`, and
`gc.build.brainstorming_path`. On a repeated attempt, treat the existing
`gc.build.design_path` as the canonical design candidate and revise it in place.
Use only paths recorded on the workflow root or the claimed bead.
Do not guess prior bead ids or worktree paths.

Resolve source scope from root metadata. If `gc.var.convoy_id` is set, run
`gc convoy status <launch-convoy-id> --json`. Treat every direct launch-convoy
member in `.children[]` as a source target and run
`gc bd show <source-target-id> --json` for each. Those beads are authoritative.
Only when the root formula is exactly `superpowers-planning` and has no convoy
may `gc.var.context_path` supply scope; require an existing regular file. Every
other missing or unreadable convoy must fail closed. Context never replaces a
real build root's launch convoy.

This lane maps stock Superpowers checklist items 1-5. Track each item in the
design candidate so the loop state is durable:

- project context inspected.
- Decide whether visual questions are ahead and record whether an interactive
  human gate should Offer Visual Companion in its own message. Do not send the
  offer or wait for its answer from this producer lane; if later accepted, use the
  installed Visual
  Companion guidance for questions that benefit from visuals.
- identify one clarifying question at a time when answers are needed and record
  it in the candidate.
- two or three approaches with tradeoffs and a recommendation.
- recommended design presented in sections scaled to the task and written to
  the artifact.

For headless or autonomous runs, the supplied target, repository context,
tests and acceptance criteria are authoritative. Do not invent answers, invoke
the stock skill's user-question gates, or create extra requirements.
Never ask a human a question or wait for a reply from this lane in any
interaction mode.
If the inputs fully determine the outcome, record the autonomous approval basis.
If a human answer is required, record the exact unresolved question, leave the
design unapproved, and still complete this producer lane so
`confirm-design-approval` can apply the configured approval mode.

On repeated attempts, read the canonical previous design candidate plus the
latest design approval or revision summary when its path is present in workflow
root metadata, then revise that candidate in place. Do not discard answered
questions, approach tradeoffs, visual-companion decisions, or approved sections
from earlier attempts.

Write or update a design candidate artifact under the brainstorming artifact
directory. Include requested outcome, constraints, non-goals, design sections,
approach tradeoffs, acceptance criteria, unresolved questions, and approval
status.

This artifact represents the stock written design-doc state. The downstream
spec lane may mirror it to `docs/superpowers/specs/` when the target repo and
run instructions make that safe.

Before closing, update the exact claimed bead id with the lane metadata:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'design_review.output_path=<design-candidate path>'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Superpowers design candidate written.'
```

Do not pass `--metadata` or `--set-metadata` to `gc bd close`. Do not set
`design_review.verdict`; the approval lane owns the loop verdict.

Do not invoke provider-native subagents or upstream plugin runtime commands.
This Gas City lane owns the brainstorming pass.
