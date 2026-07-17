Finalize the approved Superpowers requirements artifact.

Validate that workflow root metadata points to an existing requirements artifact
and that the artifact is approved by the written-spec loop. On success,
preserve the normalized requirements path and approval metadata for the
downstream planning lane.

Approval metadata and file existence are not artifact validation. Read the
exact `gc.build.requirements_path` (fallback `gc.var.requirements_path`) from
the workflow root; do not validate an attempt-local substitute. Then read the
launcher rig root from its `gc.work_dir`. If that work directory is a per-step
worktree without the check, walk to the nearest ancestor containing
`.gc/scripts/checks/build-requirements-source-valid.sh`. From that launcher rig root, run
the same canonical check used by the Ralph control:

```bash
GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-requirements-source-valid.sh
```

The checker accepts context-only provenance only when the workflow root formula
is exactly `superpowers-planning` and `gc.var.context_path` resolves to an
existing regular file. Every real build root still requires its reserved launch
convoy and exact source-bead traces.

On a failed validation, repair every validation error before closing: preserve
the approved requirements content while fixing the required YAML front matter,
trace coverage, Markdown coverage table, or required section order. Rerun the
validator and set `gc.outcome=pass` only after it succeeds. On a repeated
attempt, also read the parent validation control bead's `gc.attempt_log`; do
not treat a missing attempt description as permission to skip validation.

This lane represents the stock brainstorming terminal state, where Superpowers
would invoke `writing-plans`. In Gas City, do not invoke that skill directly;
close this expansion and let the parent formula's plan step route the approved
requirements artifact to `superpowers.writing-plans`.

This is stock checklist item 9 expressed through the Gas City parent formula:
the transition is durable metadata plus the next graph step, not a provider
native skill invocation.

Do not invoke provider-native subagents. Close this sink step with
`gc.outcome=pass`.
