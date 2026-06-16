Confirm Superpowers spec approval.

HARD STOP: this bead is not complete until the exact claimed bead id has
terminal metadata and that metadata has been read back from `bd show`. Closing
without `gc.outcome`, `design_review.verdict`, and
`design_review.output_path` makes the approval loop retry forever.

Do not run `.gc/scripts/checks/design-review-approved.sh` before writing this
bead's terminal metadata; that script checks this approval bead and will report
that another pass is needed until `design_review.verdict` is present. Do not use
`bd update --metadata` for this lane. Use `--set-metadata` exactly as shown
below so the workflow step outcome and approval metadata are all present.

If autonomous approval conditions are satisfied, the final action must be this
shape. Replace only `<approval-summary path>` after writing the summary:

```bash
bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'design_review.verdict=done' \
  --set-metadata 'design_review.output_path=<approval-summary path>' \
  --set-metadata 'design_review.approval_mode=autonomous' \
  --set-metadata 'gc.continuation_group=superpowers-spec-fixes'
bd show "$CLAIMED_BEAD_ID" --json | jq -e '
  (if type == "array" then .[0] else . end) as $bead |
  $bead.metadata["gc.outcome"] == "pass" and
  $bead.metadata["design_review.verdict"] == "done" and
  ($bead.metadata["design_review.output_path"] | type == "string" and length > 0)
'
bd close "$CLAIMED_BEAD_ID" --reason 'Superpowers spec approved.'
```

This lane represents the stock `User reviews spec?` approval gate after the
spec review and feedback pass, corresponding to stock checklist item 8. A
change request loops back through the written spec pass; approval lets the
workflow transition to downstream planning. Use workflow root metadata
`gc.var.brainstorming_approval_mode` when present; otherwise default to
`autonomous`.

In `interactive` mode, use the passive wait + mail human gate pattern. This is
not a timeout-driven task.

1. Before waiting, update workflow root metadata with:
   - `gc.build.spec_gate_status=waiting-human`
   - `gc.build.spec_gate_bead_id=<this bead id>`
   - `gc.build.spec_gate_artifact_path=<approval-summary path>`
   - preserve any existing `gc.build.spec_gate_mail_sent=true`
2. Park the current session so idle handling does not recycle it while the
   human decides:
   ```bash
   SESSION_TARGET="${GC_SESSION_ID:-${GC_SESSION_NAME:-}}"
   SESSION_ATTACH="${GC_SESSION_NAME:-$SESSION_TARGET}"
   WAIT_NOTE="Waiting for human approval of Superpowers written spec on bead $GC_BEAD_ID."
   if [ -n "$SESSION_ATTACH" ]; then
     WAIT_NOTE="$WAIT_NOTE Resume with: gc session attach $SESSION_ATTACH"
   fi
   if [ -n "$SESSION_TARGET" ] && ! gc wait list --session "$SESSION_TARGET" | grep -Fq "$WAIT_NOTE"; then
     gc session wait "$SESSION_TARGET" \
       --sleep \
       --on-beads "$GC_BEAD_ID" \
       --note "$WAIT_NOTE"
   fi
   ```
3. If workflow root metadata does not already have
   `gc.build.spec_gate_mail_sent=true`, send exactly one mail with
   `gc mail send human ...`. Include the written spec path, spec review report
   path, approval summary path, workflow root id, this bead id, and the
   requested response options: approve, request changes, or reject. After
   sending, update workflow root metadata with
   `gc.build.spec_gate_mail_sent=true` and `gc.build.spec_gate_mail_to=human`.
4. Wait for explicit human feedback from the active session or mail thread. If
   the session idles, detaches, or
   restarts before the human responds, do not close this bead. A resumed worker
   must read the gate metadata and continue waiting from this gate.
5. Use `done` only after explicit approval by setting
   `design_review.verdict=done`. If the human requests changes, record the
   requested revisions in the approval summary and close with
   `design_review.verdict=iterate`. Close fail only for explicit rejection or
   abort, not for silence.

In `autonomous` mode, approve only when the spec review has no required issues,
the apply pass made no required changes in this attempt, and the requirements
artifact has no unresolved questions. Otherwise close with
`design_review.verdict=iterate`.

Use the supported `bd list` metadata filters below to inspect predecessor lanes.
Do not use `bd list --root`; that flag is not supported by the Beads CLI.
Select only `gc.scope_role=member` so scope-check control beads do not get
mistaken for the review or apply lane:

```bash
bd list --all --has-metadata-key gc.step_id \
  --metadata-field gc.root_bead_id="$CLAIMED_ROOT_BEAD_ID" \
  --metadata-field gc.step_id=requirements.review-written-spec \
  --metadata-field gc.scope_role=member \
  --json
bd list --all --has-metadata-key gc.step_id \
  --metadata-field gc.root_bead_id="$CLAIMED_ROOT_BEAD_ID" \
  --metadata-field gc.step_id=requirements.apply-spec-feedback \
  --metadata-field gc.scope_role=member \
  --json
```

When iterating, write a concise spec revision summary that the next
`write-requirements-spec` attempt can apply directly. The summary must name the
specific requirements sections, ambiguity, contradiction, or scope issue that
caused the loopback.

On approval, write an approval summary, mark the requirements artifact approved,
and update workflow root
metadata with `gc.build.requirements_status=approved`,
`gc.build.requirements_path=<absolute path>`,
`gc.build.spec_gate_status=approved`, and a short requirements summary. For a
human-requested iteration, update `gc.build.spec_gate_status=revision_requested`.

Before closing, update the exact claimed bead id with the lane metadata, then
verify it from `bd show "$CLAIMED_BEAD_ID" --json`. The approval verdict
metadata is `design_review.verdict=done|iterate`; for approval, verify
`design_review.verdict == "done"`:

```bash
bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'design_review.verdict=done' \
  --set-metadata 'design_review.output_path=<approval-summary path>' \
  --set-metadata 'design_review.approval_mode=autonomous' \
  --set-metadata 'gc.continuation_group=superpowers-spec-fixes'
bd show "$CLAIMED_BEAD_ID" --json | jq -e '
  (if type == "array" then .[0] else . end) as $bead |
  $bead.metadata["gc.outcome"] == "pass" and
  $bead.metadata["design_review.verdict"] == "done" and
  ($bead.metadata["design_review.output_path"] | type == "string" and length > 0)
'
bd close "$CLAIMED_BEAD_ID" --reason 'Superpowers spec approved.'
```

If the spec needs another pass, set `design_review.verdict=iterate` instead of
`done` and name the required correction in the approval summary and close
reason. For iteration, run the same read-back check with
`.metadata["design_review.verdict"] == "iterate"`. If the read-back check
fails, do not close the bead; rerun `bd update "$CLAIMED_BEAD_ID"` and verify
again. Do not pass `--metadata` or `--set-metadata` to `bd close`.

Do not invoke provider-native subagents or upstream plugin runtime commands.
This Gas City lane owns the approval decision.
