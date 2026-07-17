Finalize the gstack sprint.

Read the canonical final report path from workflow root metadata
`gc.build.final_report_path` and write the report there. Do not replace it with
an attempt-local path. Include the methodology, interaction_mode, review_mode,
requirements path, plan path, decomposition path, implementation summary,
review report, QA report, release readiness report, tests run, changed files,
residual risks, and next human action.

The report should explain that garrytan/gstack role behavior was adapted into
Gas City fanouts and persistent beads. Keep it useful for someone using
automated factories for the first time.

The report must be Markdown with YAML front matter valid for
`gc.build.final-report.v1`, not JSON. Its first line must be `---`, with a
closing `---` before the Markdown body. Use nested YAML mappings with this
top-level shape:

```yaml
---
schema: gc.build.final-report.v1
workflow:
  id: <workflow-root-id>
  formula: <root-workflow-formula>
methodology:
  pack: gstack
  name: gstack-build
producer:
  formula: gstack-build
  stage: finalize
  attempt: <current positive gc.attempt for this finalize stage>
status: approved
trace:
  upstream:
    - path: <canonical-build-artifact-path>
      hash: sha256:<artifact-digest>
      ids: [<actual-source-id>]
  coverage:
    - id: <actual-source-id>
      status: covered
---
```

Trace the canonical absolute `gc.build.implementation_summary_path` and
`gc.build.review_report_path` exactly once each, using a freshly computed
`sha256:<digest>` of each exact file. An earlier artifact, a byte-identical copy
at another path, or a path without its current digest is stale and must block
finalization.

Use `status: approved` only when the canonical requirements, plan,
decomposition, implementation summary, review, QA, and release-readiness
evidence support a successful build. Use `status: blocked` and keep failure
metadata when required evidence failed.

Use these mutually exclusive terminal branches. A review, QA, or readiness
expansion can successfully deliver a report without authorizing build success.

Successful branch:

- Require the canonical review artifact to have `status: approved`, including
  when `gc.var.review_mode=report` and report delivery is recorded separately.
- Require QA and release readiness to have semantic approval and require all
  implementation evidence below to pass.
- Write the final artifact with `status: approved`, validate it, apply only the
  completed/success lifecycle update below, and close the claimed finalize step
  with `gc.outcome=pass`.

Blocked branch:

- A report-mode review artifact with `status: changes_required` is successful
  report delivery, not implementation approval. Write the final artifact with
  `status: blocked`, record both final-report paths, and run the installed
  artifact check against that blocked artifact.
- After the blocked artifact validates, atomically record at least
  `gc.outcome=fail`, `gc.build.status=blocked`,
  `gc.build.finalize_status=failed`, `gc.build.finalize_outcome=failure`,
  `gc.build.repair_status=repairable`,
  `gc.restart.entrypoint=build-from-review`,
  `gc.restart.reason=review_changes_required`,
  `gc.restart.review_report_path=<canonical review report path>`,
  `gc.blocked_reason=code_review_changes_required`, and
  `gc.failure_class=review_iteration_needed` on the workflow root.
- A review artifact with `status: blocked`, unresolved report-mode QA or release
  readiness findings, missing implementation evidence, or a validation failure
  must use the same failure-only lifecycle shape with
  `gc.build.repair_status=blocked` and a precise blocked reason, failure class,
  and restart entrypoint.
- Set the claimed finalize step to `gc.outcome=fail`, close it, and stop. This
  branch must not set `gc.outcome=pass`, must not set
  `gc.build.finalize_status=completed`, and must not set
  `gc.build.finalize_outcome=success` anywhere. A validated report with
  findings must never become a completed build.

Re-read runtime implementation state before approving. The launch requirements
must trace every direct member of `gc.var.convoy_id`. The implementation convoy
IDs and `gc.build.implementation_member_ids` must agree with `gc convoy status`,
the convoy and all exact members must be closed, and every member must retain
worktree-bound proof whose recorded worktree, full commit SHA, and summary
match the authoritative implementation worktree. Never approve evidence or QA
fixes produced only in the launcher checkout. Require the canonical artifact
at `gc.build.implementation_summary_path` to trace every current per-item
summary with its current `sha256` digest and to name every member's current
worktree and full commit; pre-QA or pre-review provenance is stale.

Every `trace.upstream` entry must contain a path and scheme-qualified hash.
Preserve actual source IDs verbatim; never invent, substitute, or renumber
them. Account for each declared ID exactly once in `trace.coverage`; when no
source declares IDs, omit `ids` and use `coverage: []`. Every non-`covered`
entry requires a rationale. Include one Markdown table whose `ID` and `Status`
pairs exactly match `trace.coverage`:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Only include the example data row when coverage is non-empty, and replace the
placeholder with an actual ID. When coverage is empty, do not add a data row;
omit the table or use only its header and separator.

Use these schema-required second-level headings in this exact order:

- `## Summary`
- `## Outcome`
- `## Artifacts`
- `## Remaining Risks`

Before closing, resolve the launcher rig root from workflow root metadata
`gc.work_dir`. If it names a step worktree without the check, use the nearest
ancestor containing `.gc/scripts/checks/build-artifact-valid.sh`. Read the exact
current bead ID from the startup claim output and substitute it literally
below; shell variables from earlier tool calls do not persist. Then run:

```bash
GC_BEAD_ID=<exact-claimed-bead-id> <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Fix every validation error against the canonical `gc.build.final_report_path`.
After validation, follow the matching terminal branch above. Only after an
approved final artifact and all required evidence pass may the successful
branch reconcile workflow root lifecycle metadata in one update:

```bash
gc bd update <workflow-root-id> \
  --set-metadata 'gc.build.final_report_path=<canonical final report path>' \
  --set-metadata 'gc.build.status=completed' \
  --set-metadata 'gc.build.finalize_status=completed' \
  --set-metadata 'gc.build.finalize_outcome=success' \
  --unset-metadata gc.blocked_reason \
  --unset-metadata gc.failure_class \
  --unset-metadata gc.build.repair_status \
  --unset-metadata gc.restart.entrypoint \
  --unset-metadata gc.restart.reason \
  --unset-metadata gc.restart.review_report_path \
  --unset-metadata gc.restart.review_fix_formula \
  --unset-metadata gc.restart.implementation_target
```

Then set the claimed finalize step to `gc.outcome=pass` and close it with the
sprint report path. This update and pass outcome belong only to the successful
branch. On validation or evidence failure, retain failure markers and use the
blocked branch; never emit completed/success metadata.

Do not invoke provider-native subagents.

Artifact validation: this stage is gated by the shipped `../assets/scripts/checks/gstack-build-state-valid.sh`, which first validates the artifact recorded at `gc.build.final_report_path` against schema `gc.build.final-report.v1`, then revalidates launch-source trace, exact implementation membership and closure, and authoritative worktree proof. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact or fail closed; never manufacture missing implementation proof. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
