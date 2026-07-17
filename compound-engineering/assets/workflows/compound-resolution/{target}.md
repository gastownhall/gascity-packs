Finalize the Compound Engineering build against the canonical report.

Read the exact report path from workflow root metadata
`gc.build.final_report_path`. Require the synthesized report to exist at that
path; never replace it with an attempt-local artifact or a `docs/solutions`
document. Read the synthesis verdict, artifact inventory, review-resolution
result, test evidence, and publish-readiness evidence before deciding the final
outcome.

Resolve the launcher rig root from workflow root metadata `gc.work_dir`. If it
names a per-step attempt worktree without the validator, walk to the nearest
ancestor containing `.gc/scripts/checks/build-artifact-valid.sh`. From that
launcher rig root run:

Read the exact current bead ID from the startup claim output. In the same shell
invocation, substitute it literally for the placeholder below; variables from
earlier tool calls do not persist.

```bash
export CLAIMED_BEAD_ID='<exact-current-bead-id>'
GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

On repair attempts (`gc.attempt` greater than 1), first read `gc.attempt_log`
on the validation-loop control bead and repair the report in place at the exact
`gc.build.final_report_path`. Do not change the root path to bypass validation.
The repaired report's `producer.attempt` must equal this terminal's current
positive `gc.attempt`. It must trace the canonical absolute
`gc.build.implementation_summary_path` and `gc.build.review_report_path`
exactly once each with their freshly computed `sha256:<digest>` values; an
earlier artifact or an equivalent copy at another path is stale.

Only after the canonical `gc.build.final-report.v1` report validates and all
required evidence succeeds, reconcile the build-base workflow root lifecycle
metadata in one update:

```bash
gc bd update <workflow-root-id> \
  --set-metadata 'gc.build.final_report_path=<canonical final report path>' \
  --set-metadata 'gc.build.status=completed' \
  --set-metadata 'gc.build.finalize_status=completed' \
  --set-metadata 'gc.build.finalize_outcome=success' \
  --unset-metadata gc.blocked_reason \
  --unset-metadata gc.failure_class
```

The artifact's top-level `status: approved` is distinct from the workflow root
lifecycle value `gc.build.status=completed`. Explicitly unset both stale
failure markers because metadata updates otherwise merge with prepare-stage
state.

Then close this expansion target with `gc.outcome=pass`, the canonical report
path, and the final success verdict. If validation or any required evidence
fails, do not clear `gc.blocked_reason` or `gc.failure_class`; record
`gc.build.finalize_status=failed`, retain the failure evidence, and close the
target with `gc.outcome=fail`.
