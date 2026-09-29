Finalize the gstack plan review.

Verify the latest plan-review loop approved the plan or clearly recorded
remaining required fixes. Record the approved plan-review summary path on the
workflow root for decomposition and the final sprint report.

Close with `gc.outcome=pass`.

Do not invoke provider-native subagents.

Plan artifact validation: this step is gated by
`.gc/scripts/checks/build-artifact-valid.sh`, which validates the plan
recorded at workflow root metadata `gc.build.plan_path` (fallback
`gc.var.plan_path`) against schema `gc.build.plan.v1`. Plan-review fix lanes
edit the plan in place, so re-validate it here before closing:

- From `$GC_RIG_ROOT`, run the artifact validator with the claimed bead id and
  fix any error before setting `gc.outcome=pass`:
  `GC_BEAD_ID=<claimed-step-id> .gc/scripts/checks/build-artifact-valid.sh`.
- Repair the plan in place and keep its YAML front matter intact. Its
  front-matter `status` must be one of `draft`, `questions`, `approved`,
  `changes_required`, `blocked`, or `superseded`. Replace any other value
  (for example `reviewed`) with the allowed status that matches the review
  outcome (`approved` for an approved plan).
- On repair attempts (`gc.attempt` greater than 1), first read the validator
  errors from `gc.attempt_log` on the validation loop control bead (the
  dependent of this step bead) and fix every listed error in place.
