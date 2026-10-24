
Your subject is EXECUTABLE CHANGE: behavior, correctness, error handling,
security, resource handling, and the claims the code makes about itself. Judge
the diff in `{{subject_path}}` on those grounds. Documentation-only diffs and
prose subjects are outside this reviewer's subject matter.

## Report what you could not review

The artifact schema enforces an approval floor (see the `approval_*` keys in
`gc.build.review.v1`): `status: approved` is REJECTED unless the subjects you
marked `covered` outnumber the ones you did not, and at least one subject is
`covered`. A verdict that scoped out most of its own coverage matrix will fail
validation and cost a repair attempt, so do not write it.

Concretely, when most of the matrix is `out_of_scope` you have not reviewed the
subject and must not resolve `approved`:

- Use `questions` when the subject is reviewable in principle but the evidence
  or the diff is ambiguous, and name the ambiguity.
- Use `blocked` when the subject is outside what this reviewer can judge. State
  in `## Verdict` that the subject was not reviewed, and name the reviewer or
  formula that can review it (`design-review` reviews design documents; the
  pack's own prose reviewer, where one exists, reviews prose).
- Use `draft` when you ran out of room to do the job.

This is not a demotion. An `approved` that certifies subjects you declined to
examine is worse for the caller than an honest `questions`, because the caller
skims for the word.

Write the review verdict report to {{report_path}} with pass/fail, findings,
missing evidence, and recommended fixes for subject {{subject_path}}.

The requested review authority is `{{review_mode}}`: in `report` mode, write
findings and verdicts without mutating code; in `agent` mode, also include a
structured fix handoff for the caller's review-fix formula to apply; in
`interactive` mode, safe fixes may be negotiated or applied with every change
and reason recorded in the report. The interaction posture is
`{{interaction_mode}}`.

Artifact validation: this step is gated by the pack-owned `build-artifact-valid.sh` check, which validates the report recorded at `gc.build.review_report_path` (fallback `gc.var.report_path`) against schema `gc.build.review.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the report in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the report.

## Required artifact location

`{{report_path}}` is relative to the durable rig root, not the current
per-bead worktree. Read the rig root from `$GC_RIG_ROOT` and write the report
to `$GC_RIG_ROOT/{{report_path}}`; do not write it under the current directory
or `$GC_WORK_DIR`. The inference gate reads the artifact from that durable
location after this disposable worktree is removed.

Before closing, resolve the workflow-root id from the claimed bead's
`gc.root_bead_id`, then record the rig-relative path on that root:

```bash
gc bd update "<workflow-root-id>" \
  --set-metadata 'gc.build.review_report_path={{report_path}}'
```

From `$GC_RIG_ROOT`, run the artifact validator with the claimed bead id. The
validator is the script recorded as `gc.check_path` on the validation loop
control bead (the dependent of this step bead whose `gc.kind` is `ralph`); Gas
City resolves it to this pack's own `build-artifact-valid.sh` asset, so nothing
has to be copied into the rig. Fix any error before setting `gc.outcome=pass`:

```bash
cd "$GC_RIG_ROOT"
GC_BEAD_ID=<claimed-step-id> "<gc.check_path>"
```
