Finalize the BMAD build and write its canonical final report.

Read the exact report path from workflow root metadata
`gc.build.final_report_path`. Write the report there and do not replace it with
an attempt-local path. Read the canonical requirements, plan, decomposition,
implementation-readiness report, implementation summary, and review report.
Include their paths and hashes, implementation convoy and source anchors,
changed files, tests run, review verdict, residual risks, and next human action.

Write Markdown with YAML front matter valid for
`gc.build.final-report.v1`, not JSON. The artifact's first line must be `---`, followed by
a closing `---` before the Markdown body. Use nested mappings with this
top-level shape:

```yaml
---
schema: gc.build.final-report.v1
workflow:
  id: <workflow-root-id>
  formula: bmad-build
methodology:
  pack: bmad
  name: bmad-build
producer:
  formula: bmad-build
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

Use `status: approved` only when readiness approved, all required
implementation evidence passed, and the review contract permits completion.
Otherwise use `status: blocked`, retain failure metadata, and do not mark the
build completed.

Use these mutually exclusive terminal branches. A successful review-expansion
step only proves that it delivered a valid report; it does not authorize a
top-level build pass when that report still requires changes.

Successful branch:

- Require the canonical review artifact to have `status: approved`, including
  when `gc.var.review_mode=report` and
  `gc.build.code_review_status=reported` records report delivery.
- Require readiness approval and successful implementation evidence.
- Write the final artifact with `status: approved`, record
  `gc.build.repair_status=not_needed` when no review fix ran or
  `gc.build.repair_status=approved` when the fix loop resolved findings. Apply
  only the completed/success lifecycle update below, and close the claimed step
  with `gc.outcome=pass`.

Blocked branch:

- A review artifact with `status: changes_required` or `status: blocked`, a
  readiness failure, missing implementation evidence, or validation failure
  cannot use the successful branch.
- For report-mode `changes_required`, write the final artifact with
  `status: blocked` and atomically record at least
  `gc.outcome=fail`, `gc.build.status=blocked`,
  `gc.build.finalize_status=failed`, `gc.build.finalize_outcome=failure`,
  `gc.build.repair_status=repairable`,
  `gc.restart.entrypoint=build-from-review`,
  `gc.restart.reason=review_changes_required`,
  `gc.restart.review_report_path=<canonical review report path>`,
  `gc.blocked_reason=code_review_changes_required`, and
  `gc.failure_class=review_iteration_needed` on the workflow root.
- For a blocked review or other failed prerequisite, use the same failure-only
  lifecycle shape with `gc.build.repair_status=blocked` and a precise restart
  reason and failure class.
- Close the claimed step with `gc.outcome=fail`. This branch must not set
  `gc.outcome=pass`, must not set `gc.build.finalize_status=completed`, and
  must not set `gc.build.finalize_outcome=success` anywhere.

Every `trace.upstream` entry must contain `path` and a scheme-qualified `hash`.
Preserve actual source IDs verbatim; never invent, substitute, or renumber
them. Every declared ID must appear exactly once in `trace.coverage`; when no
source declares IDs, omit `ids` and use `coverage: []`. Give every
non-`covered` row a rationale.

Include one Markdown coverage table whose `ID` and `Status` pairs exactly match
the YAML coverage:

| ID | Status |
| --- | --- |
| <actual-source-id> | covered |

Only include the example data row when coverage is non-empty, replacing the
placeholder with an actual ID. When coverage is empty, omit the table or use
only its header and separator; do not add a placeholder data row.

Use these schema-required second-level headings in this exact order:

- `## Summary`
- `## Outcome`
- `## Artifacts`
- `## Remaining Risks`

Before closing, resolve the launcher rig root from workflow root metadata
`gc.work_dir`. If it names an attempt worktree without the validator, walk to
the nearest ancestor containing
`.gc/scripts/checks/build-artifact-valid.sh`. Read the exact current bead ID
from the startup claim output and assign it literally in the same shell call;
shell variables from earlier tool calls do not persist. Run:

```bash
CLAIMED_BEAD_ID=<exact-claimed-bead-id>; GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Fix every validation error at `gc.build.final_report_path`. On repair attempts
(`gc.attempt` greater than 1), read validator errors from `gc.attempt_log` on
the dependent validation-loop control bead and repair the same report in
place. Two bounded repair attempts follow the first failure.

Only after the final report validates and all evidence is successful, reconcile
workflow root lifecycle metadata in one update:

```bash
gc bd update <workflow-root-id> \
  --set-metadata 'gc.build.final_report_path=<canonical final report path>' \
  --set-metadata 'gc.build.status=completed' \
  --set-metadata 'gc.build.finalize_status=completed' \
  --set-metadata 'gc.build.finalize_outcome=success' \
  --set-metadata 'gc.build.repair_status=<not_needed-or-approved>' \
  --unset-metadata gc.blocked_reason \
  --unset-metadata gc.failure_class \
  --unset-metadata gc.restart.entrypoint \
  --unset-metadata gc.restart.reason \
  --unset-metadata gc.restart.review_report_path \
  --unset-metadata gc.restart.review_fix_formula \
  --unset-metadata gc.restart.implementation_target
```

Then set the claimed step to `gc.outcome=pass` and close it. This update belongs
only to the successful branch. If validation or required evidence fails, use
the blocked branch above; never emit completed lifecycle metadata on failure.

Do not invoke provider-native subagents or upstream BMAD runtime commands.
