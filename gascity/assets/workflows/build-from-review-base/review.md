This is the `build-from-review-base` review stage.

Review the implementation against:

- requirements_path: {{requirements_path}}
- plan_path: {{plan_path}}
- plan_review_path: {{plan_review_path}}
- decomposition_path: {{decomposition_path}}
- implementation_summary_path: {{implementation_summary_path}}
- code_review_formula: {{code_review_formula}}
- review_fix_formula: {{review_fix_formula}}
- implementation_formula: {{implementation_formula}}
- implementation_item_formula: {{implementation_item_formula}}
- review_mode: {{review_mode}}
- interaction_mode: {{interaction_mode}}
- max_iterations: {{max_iterations}}
- review_repair_policy: {{review_repair_policy}}

Use the selected code review methodology to produce a review verdict and
findings. This stage records the review result; the following `repair-review`
stage owns any selected review-fix loop, restart handoff, or blocked repair
state.

For `review_mode=report`, write findings and verdicts without mutating code.
For `review_mode=agent`, write a structured fix handoff for the caller or
selected fix loop. For `review_mode=interactive`, safe fixes may be negotiated
or applied, but every change and reason must be recorded.

Close this step only when the implementation has a concrete review verdict:
`approved`, `changes_required`, or `blocked`. Record the review report path,
verdict, unresolved findings, drift observations, and any existing fix-attempt
count on the workflow root metadata.

Findings convention: every entry under `## Findings` is a bullet carrying
`**Severity:** blocker|major|minor|nit`, `**Evidence:** path:line`, and
`**Required fix:** ...`. Include a `trace.upstream` entry for the review
subject: `{path: <worktree>, hash: git:<HEAD>, role: review-subject}`.

Slot contract: `review` is the review composition slot. When an extending
formula replaces this step with `[[compose.expand]] target = "review"`, the
expansion's terminal `{target}` step owns the `gc.build.review.v1` gate
(`.gc/scripts/checks/build-artifact-valid.sh`,
`gc.build.artifact_path_keys=gc.build.review_report_path`) and must record the
keys below; when this step runs unexpanded it records them itself. Required:
`gc.build.review_report_path`, `gc.build.review_report_sha256`,
`gc.build.review_verdict=approved|changes_required|blocked`,
`gc.build.review_initial_findings=blocker=<n>,major=<n>,minor=<n>,nit=<n>` (from
`.gc/scripts/review_findings_counts.py findings <report>`). Optional:
`gc.build.review_synthesis_path`, `gc.build.review_synthesis_sha256`,
`gc.build.review_scorecard_path`, `gc.build.review_scorecard_sha256`,
`gc.build.review_scorecard_decision=approve|request_changes|block`,
`gc.build.review_scorecard_score=<0-1000>`. If a required reviewer could not run
because its provider/model was unavailable, write `status: blocked`, record
`gc.build.review_state=review_unavailable`, `gc.failure_class=review_unavailable`,
`gc.failure_reason=model_unavailable`; do not invent findings.

Parser resolution (the same chain every review-slot producer uses): the
rig-installed copy first, then the base pack checkout under the work dir, then
the extending pack's mirror.

```bash
# The severity/scorecard parser: the rig-installed copy first, then the base
# pack checkout under the work dir, then the pack mirror.
COUNTS=".gc/scripts/review_findings_counts.py"
if [ ! -f "$COUNTS" ]; then COUNTS="${GC_WORK_DIR:-.}/gascity/assets/scripts/review_findings_counts.py"; fi
if [ ! -f "$COUNTS" ]; then COUNTS="${PACK_ROOT:?no review_findings_counts.py on the rig, under GC_WORK_DIR, or PACK_ROOT}/scripts/review_findings_counts.py"; fi
python3 "$COUNTS" findings <report>
```

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.review_report_path` against schema `gc.build.review.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
