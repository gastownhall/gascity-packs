Finalize the Compound Engineering plan-review expansion.

Verify the latest synthesized verdict is approved, promote the plan-review
artifact path to the workflow root, and close this expansion target. If the loop
exhausted attempts or has unresolved required findings, record a failing review
outcome — honestly — with the report path.

Use workflow root metadata `gc.build.plan_review_report_path` and
`gc.build.plan_review_apply_summary_path`.

On SUCCESS (latest verdict approves), update the workflow root with all of the
following, then close with `gc.outcome=pass`:

- `gc.build.plan_review_status=approved`
- `gc.build.plan_review_approved_at=<UTC timestamp>`
- `gc.build.plan_review_path=<gc.build.plan_review_report_path value>` — promote
  the approved plan-review artifact path to root so the downstream decompose
  stage can read it at runtime (symmetric with `gc.build.plan_path`; dip-5hkepo).
- `gc.var.plan_review_path=<same path>`

Record them in one command, e.g.
`bd update "<workflow-root-id>" --set-metadata "gc.build.plan_review_status=approved" --set-metadata "gc.build.plan_review_path=<path>" --set-metadata "gc.var.plan_review_path=<path>" --set-metadata "gc.build.plan_review_approved_at=<UTC timestamp>"`.
Do not use `bd update --metadata 'key=value'`; `--metadata` only accepts a JSON
object.

On FAILURE (the loop exhausted its attempts or unresolved required findings
remain — the plan review did NOT converge to approval), record the failing
outcome HONESTLY so the plan-review-approved gate (dip-duj3e6) and any downstream
consumer see the truth instead of a stale `draft`/`approved`. Update the workflow
root with all of the following, then close with `gc.outcome=fail`:

- `gc.build.plan_review_status=failed` — authoritative post-review verdict; the
  status is now honest (approved XOR failed), so the gate's `status==approved`
  predicate is self-sufficient.
- `gc.build.plan_status=failed` — un-approve the pre-review self-declaration
  written at plan-authoring time, so `plan_status` and `plan_review_status` never
  disagree (closes the stale-approved trap). `gc.build.plan_review_status` remains
  the authoritative field; this is defense-in-depth.
- Keep `gc.build.plan_review_report_path` pointing at the report for triage.

Record them in one command, e.g.
`bd update "<workflow-root-id>" --set-metadata "gc.build.plan_review_status=failed" --set-metadata "gc.build.plan_status=failed"`,
then `bd close "<claimed-step-id>" --reason "<why the review did not converge>"`
after setting `gc.outcome=fail` on the claimed step with `bd update`. Do NOT close
with `--metadata`/`--set-metadata`. Do NOT record `plan_review_status=approved`
on the failing branch.

Do not invoke provider-native subagents or upstream plugin runtime commands.
This graph stage is the delegation mechanism.
