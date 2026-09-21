This is the `build-from-review-base` finalize stage.

Synthesize the continuation result from the prerequisite artifacts,
implementation evidence, review reports, fix attempts, drift checks, and
publish intent.

The final report must state which continuation entrypoint started the run and
which upstream stages were skipped because their approved artifacts already
existed. Include the requirements path, plan path, plan-review path when
available, decomposition path, implementation convoy ID when available,
implementation evidence, review verdict, remaining risk, publish
authorization, and next action.

Do not close the workflow root with `gc.outcome=pass` when the review verdict
is `blocked`, any implementation drain failed, required implementation evidence
is missing, the review verdict is `changes_required` without recorded review
evidence and a post-fix `gc.build.repair_status`, `gc.build.review_state` is
empty, `review_blocked`, or `review_unavailable`, or `gc.build.repair_status` is
anything other than `not_needed`, `approved`, `fixed`, or `residual`. In those
cases, write a final report with `status: blocked`, record `gc.outcome=fail`,
`gc.build.status=blocked`, `gc.failure_class` with the machine-readable reason
(preserving `review_unavailable` and `gc.failure_reason=model_unavailable` when
the review or fix stage recorded them), and preserve restart metadata such as
`gc.restart.entrypoint`, `gc.restart.reason`, and the relevant artifact paths.

Only record a passing terminal outcome when all prerequisite artifacts exist,
implementation evidence is present, `gc.build.review_verdict` is `approved` or
`changes_required` with review evidence recorded (`gc.build.review_report_path`,
`gc.build.review_report_sha256`, `gc.build.review_initial_findings`), and
`gc.build.repair_status` is `not_needed`, `approved`, `fixed`, or `residual`.
On pass, record `gc.build.status` from the review state written by
`repair-review`:

- `gc.build.review_state=reviewed_approved` (repair status `not_needed` or
  `approved`) -> `gc.build.status=approved`.
- `gc.build.review_state=reviewed_fixed_unverified` (repair status `fixed`,
  `gc.build.review_post_fix_verified=false`) -> `gc.build.status=candidate`;
  `## Remaining Risks` states "fixed, unverified".
- `gc.build.review_state=reviewed_with_residual_findings` (repair status
  `residual`) -> `gc.build.status=candidate`; `## Remaining Risks` lists every
  residual finding verbatim from the review-fixes artifact with its severity and
  disposition plus `post_fix_verified`.

A candidate with residual findings is not an approval and never publish authorization.
The final-report front matter gains an additive `review:` mapping
with `report_path`, `report_sha256`, `verdict`, `review_state`, `repair_status`,
`fix_commit`, residual counts by severity, and `scorecard_decision` when
recorded.

Record terminal outcome metadata on the workflow root before closing so the
publish step can safely no-op, push, open a PR, or block with an explicit
reason without changing the workflow outcome.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.final_report_path` against schema `gc.build.final-report.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
