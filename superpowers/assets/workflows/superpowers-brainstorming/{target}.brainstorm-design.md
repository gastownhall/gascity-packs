Use the installed Superpowers brainstorming guidance to produce an approved
design candidate.

This lane maps stock Superpowers checklist items 1-5. Track each item in the
design candidate so the loop state is durable:

- project context inspected.
- Decide whether visual questions are ahead; if so, Offer Visual Companion in
  its own message before continuing; if accepted, use the installed Visual
  Companion guidance for questions that benefit from visuals.
- one clarifying question at a time when answers are needed.
- two or three approaches with tradeoffs and a recommendation.
- recommended design presented in sections scaled to the task.

For autonomous runs, do not invent answers. If the target and context fully
determine the outcome, record the autonomous approval basis. If a human answer
is required, record the exact question and leave the design unapproved.

On repeated attempts, read the previous design candidate plus the latest design
approval or revision summary, then revise that candidate in place. Do not
discard answered questions, approach tradeoffs, visual-companion decisions, or
approved sections from earlier attempts.

Write or update a design candidate artifact under the brainstorming artifact
directory. Include requested outcome, constraints, non-goals, design sections,
approach tradeoffs, acceptance criteria, unresolved questions, and approval
status.

This artifact represents the stock written design-doc state. The downstream
spec lane may mirror it to `docs/superpowers/specs/` when the target repo and
run instructions make that safe.

Before closing, update the exact claimed bead id with the lane metadata:

```bash
bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'design_review.output_path=<design-candidate path>'
bd close "$CLAIMED_BEAD_ID" --reason 'Superpowers design candidate written.'
```

Do not pass `--metadata` or `--set-metadata` to `bd close`. Do not set
`design_review.verdict`; the approval lane owns the loop verdict.

Do not invoke provider-native subagents or upstream plugin runtime commands.
This Gas City lane owns the brainstorming pass.
