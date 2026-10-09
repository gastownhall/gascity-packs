Finalize the approved Superpowers requirements artifact.

Validate that workflow root metadata points to an existing requirements artifact
and that the artifact is approved by the written-spec loop. On success,
preserve the normalized requirements path and approval metadata for the
downstream planning lane.

Artifact validation: this step is gated by
`.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact
recorded at `gc.build.requirements_path` (fallback `gc.var.requirements_path`)
against schema `gc.build.requirements.v1`. Approval metadata alone does not
satisfy it; the artifact itself must be valid.

- On repair attempts (`gc.attempt` greater than 1), read the validator errors
  from `gc.attempt_log` on the validation loop control bead (the dependent of
  this step bead) with `gc bd show "<control-bead-id>" --json` before doing
  anything else, and repair the requirements artifact in place to fix every
  listed error. For `build artifact must start with YAML front matter`, add the
  front matter described in the write-requirements-spec lane
  (`schema: gc.build.requirements.v1`, `workflow`, `methodology`, `producer`,
  `status`, `trace`) at the top of the file without rewriting the approved
  content, and add a matching Markdown coverage table and any missing required
  section.
- On every attempt, from `$GC_RIG_ROOT`, run the artifact validator with the
  claimed bead id and fix any error before setting `gc.outcome=pass`:
  `GC_BEAD_ID=<claimed-step-id> .gc/scripts/checks/build-artifact-valid.sh`.
- Do not close by re-verifying root metadata or approval stamps alone; the
  attempt passes only when the validator passes on the artifact file.

This lane represents the stock brainstorming terminal state, where Superpowers
would invoke `writing-plans`. In Gas City, do not invoke that skill directly;
close this expansion and let the parent `superpowers-build` plan step route the
approved requirements artifact to `superpowers.writing-plans`.

This is stock checklist item 9 expressed through the Gas City parent formula:
the transition is durable metadata plus the next graph step, not a provider
native skill invocation.

Do not invoke provider-native subagents. Close this sink step with
`gc.outcome=pass`.
