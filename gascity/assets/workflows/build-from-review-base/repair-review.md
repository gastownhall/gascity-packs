This is the `build-from-review-base` repair-review stage.

Read the review report, review verdict, unresolved findings, fix attempt count,
review_mode={{review_mode}}, interaction_mode={{interaction_mode}},
review_fix_formula={{review_fix_formula}}, implementation_target={{implementation_target}},
implementation_formula={{implementation_formula}}, implementation_item_formula={{implementation_item_formula}},
max_iterations={{max_iterations}}, and review_repair_policy={{review_repair_policy}}
from the workflow root metadata and artifacts.

If the review verdict is approved, do not mutate code. Record
`gc.build.repair_status=not_needed`, record `gc.build.review_state=reviewed_approved`,
preserve the approved review metadata, and close this step successfully.

Regardless of review_repair_policy: if the review verdict is `changes_required`
and review_mode=report, do not mutate code. Record
`gc.build.review_state=review_blocked`. Write a repair handoff artifact that names the selected
review_fix_formula, affected requirements, target files or work items when
known, current review report path, and the exact continuation entrypoint to
restart from. Record at least:

- `gc.build.repair_status=repairable`
- `gc.restart.entrypoint=build-from-review`
- `gc.restart.reason=review_changes_required`
- `gc.restart.review_report_path=<review report path>`
- `gc.restart.review_fix_formula={{review_fix_formula}}`
- `gc.restart.implementation_target={{implementation_target}}`

Then close this step with failure metadata so the workflow cannot finalize as a
pass without an explicit restart.

If the review verdict is `changes_required`, review_mode is agent or
interactive, and review_repair_policy=once: do not run or dispatch
review_fix_formula and do not loop. Read the artifact at
`gc.build.review_fixes_path`. `fixed` -> `gc.build.repair_status=fixed`,
`gc.build.review_state=reviewed_fixed_unverified`. `residual` ->
`gc.build.repair_status=residual`,
`gc.build.review_state=reviewed_with_residual_findings`. Close this step
successfully in both cases; do not write `gc.restart.*` or `gc.failure_class`.
Artifact missing or `blocked` -> `gc.build.repair_status=blocked`,
`gc.build.review_state=review_blocked`, `gc.outcome=fail`,
`gc.failure_class=review_repair_blocked`, `gc.restart.entrypoint=build-from-review`,
`gc.restart.reason=review_fixes_missing|review_fix_blocked`.

If review_repair_policy=loop and the review verdict is `changes_required` and
review_mode is agent or interactive, run or dispatch the selected
review_fix_formula against the recorded review findings and implementation
evidence (each iteration is one fix pass followed by one fresh re-review) until
one of these happens:

- the implementation is approved;
- review or repair returns blocked;
- max_iterations is exhausted.

Record every attempt on the workflow root metadata and in artifacts. On
approval, record `gc.build.repair_status=approved`,
`gc.build.review_state=reviewed_approved`, `gc.build.review_post_fix_verified=true`,
and the final review report path. On blocked or exhausted attempts, record
`gc.build.review_state=review_blocked` and `gc.build.repair_status=blocked`
or `gc.build.repair_status=exhausted`, `gc.outcome=fail`,
`gc.failure_class=review_repair_failed`, and restart metadata with
`gc.restart.entrypoint=build-from-review`.

If the review verdict is `blocked`, or any prerequisite review artifact,
implementation evidence, or selected formula is missing, do not invent a pass. Record `gc.build.repair_status=blocked`,
`gc.outcome=fail`, `gc.failure_class=review_repair_blocked`,
`gc.restart.entrypoint=build-from-review`, and `gc.restart.reason` with the
machine-readable blocked reason; record `gc.build.review_state=review_blocked`.
If the cause is a reviewer or fixer provider outage record
`gc.build.review_state=review_unavailable`, `gc.failure_class=review_unavailable`,
`gc.failure_reason=model_unavailable`.

Do not close the workflow root with `gc.outcome=pass` from this stage.
