Apply required Superpowers spec-review feedback to the requirements artifact.

If the review approved the artifact, perform a no-op pass and record that no
changes were needed. If the review found required issues, update only the
requirements/spec artifact and any companion brainstorming notes needed to
resolve them. Preserve traceability to the original target and do not add
unrequested scope.

Edit the requirements artifact in place and keep it valid for
`gc.build.requirements.v1`: preserve its YAML front matter (starting on the
first line), keep `trace.coverage` and the Markdown coverage table in sync, and
keep the required sections.

For every attempt, write an apply summary and, when the artifact changed, a
diff. Before closing, update the exact claimed bead id with the lane metadata:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'design_review.output_path=<apply-summary path>' \
  --set-metadata 'design_review.required_changes_applied=false'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Superpowers spec feedback pass completed.'
```

If required changes were applied, set
`design_review.required_changes_applied=true` instead. Do not pass `--metadata` or `--set-metadata` to `gc bd close`. Do not set `design_review.verdict`; the approval lane owns the loop verdict.

Keep edited build artifacts schema-valid. Stage checks and the build gate's final artifact check validate these
Markdown build artifacts, so any edit you make to one must leave it valid:

- The requirements artifact at workflow root metadata `gc.build.requirements_path`, schema `gc.build.requirements.v1`:
  front-matter `status` must be one of `draft`, `questions`, `approved`, `changes_required`, `blocked`, or `superseded`.

When you edit one of them:

- Edit it in place and preserve its YAML front matter: keep `schema`,
  `workflow`, `methodology`, `producer`, and `trace` intact, and keep
  `trace.coverage` and the Markdown `ID`/`Status` coverage table in sync.
- Use only the allowed `status` values listed above. Do not invent statuses
  such as `reviewed`; record review progress in the apply summary and bead
  metadata, not in the artifact's front matter.
- Before closing with `gc.outcome=pass`, from `$GC_RIG_ROOT`, re-run the
  validator on every build artifact you edited and fix every reported error:
  `python3 .gc/scripts/validate_build_artifact.py --schema gc.build.requirements.v1 --path "<requirements path>"`.
- On a repeated attempt (`gc.attempt` greater than 1), first read the validator
  errors from `gc.attempt_log` on the loop control bead and repair the
  artifact in place.

Do not invoke provider-native subagents. This Gas City lane owns the spec
feedback pass.
