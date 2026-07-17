Create the Superpowers implementation convoy from the approved plan.

Read the approved requirements artifact, the approved Superpowers plan, and any
existing decomposition artifact path. The plan may contain the stock
Superpowers task structure with checkbox steps for test writing, verification,
implementation, and commit. Treat those checkbox steps as execution procedure,
not as task-bead content.

Drain topology constraint: every work item runs in its own isolated,
non-integrated source-anchor worktree. Therefore each work item must be a
complete, independently verifiable vertical product slice. Do not create
package-only, implementation-only, test-only, or cleanup-only members whose
correctness depends on another member's unmerged commit. If the requested
change is one smallest coherent behavior, create one work item instead of an
artificial horizontal split.

For each `### Task N` section, create one implementation bead containing only
the work unit scope:

- task title and plan section reference
- files to create, modify, or test
- behavior or acceptance criteria covered by this task
- dependencies on earlier tasks, when required
- links to the approved requirements and plan artifacts

Do not copy the plan checkbox steps into the implementation bead. The drained
Superpowers implementation workflow supplies that procedure for each convoy
member.

Hard scoping rule: do not create implementation beads for Superpowers build
lifecycle phases. Skip or reject task sections whose title or scope is prepare,
requirements, brainstorming, written spec, plan, plan-review, decompose,
implementation workflow plumbing, review, finalization, publish, or artifact
validation. Those phases are already upstream or downstream formula steps. If a
plan accidentally includes lifecycle phases as `### Task N` sections, create
beads only for actual source-code work from the original input task or convoy
member and record the skipped lifecycle sections in the decomposition artifact.

After creating every work-item bead, create the non-empty implementation convoy
with all captured bead IDs in one command:

```bash
gc convoy create "superpowers implementation for <workflow-root-id>" <all-work-item-id...> --json
```

Do not pass `--owned`: owned convoys use a manual lifecycle and do not
auto-close after their members close, which blocks the downstream build gate.
Parse the implementation convoy ID from the JSON response. Record it on the
workflow root under both the drain input and build provenance keys in one
update:

```bash
gc bd update "<workflow-root-id>" \
  --set-metadata "gc.input_convoy_id=<implementation-convoy-id>" \
  --set-metadata "gc.build.implementation_convoy_id=<implementation-convoy-id>"
```

Read the workflow root back after this command and require both metadata keys
to name the exact newly-created implementation convoy.

Write a decomposition artifact that maps every plan task to its bead ID and
dependency edges. Close this step only after the decomposition artifact exists,
the workflow root bead has matching `gc.input_convoy_id` and
`gc.build.implementation_convoy_id` values, and the implementation convoy is
ready for drain before closing.

The decomposition artifact must be Markdown with YAML front matter, not JSON.
Use mapping objects for nested front matter.
The artifact's first line must be `---`; close the front matter with a second line containing exactly `---`
before the Markdown body. Its top-level YAML shape must be:

- `schema: gc.build.decomposition.v1`
- `workflow: {id: <workflow-root-id>, formula: <root-workflow-formula>}`
- `methodology: {pack: superpowers, name: superpowers-decomposition}`
- `producer: {formula: superpowers-build, stage: decompose, attempt: <positive integer>}`
- Set `producer.attempt` to this stage's current positive `gc.attempt`; a retry
  must update the canonical artifact to the retry's attempt before validation.
- Use `status: approved` before closing, and close only when the decomposition
  and convoy are ready. Do not invent lifecycle values such as `ready`.
- `trace: {upstream: [...], coverage: [...]}`

Every `trace.upstream[]` value must be a mapping with a path and a
scheme-qualified hash such as `bead:<id>`, `git:<revision>`, or
`sha256:<digest>`; a scalar `gc://` URI is invalid. If an upstream entry names
IDs, include each ID once in `trace.coverage` and in a Markdown table with
matching `ID` and `Status` columns. Every non-`covered` coverage entry must have
a non-empty `rationale`.

Use these required second-level sections in this exact order:

- `## Summary`
- `## Selected Downstream Formulas`
- `## Implementation Convoy`
- `## Work Items`

Additional details such as dependency graphs and skipped lifecycle sections
must remain inside those sections or follow them without replacing them.

Read and write the exact artifact path from workflow root metadata
`gc.build.decomposition_path` (fallback `gc.var.decomposition_path`). Do not
validate or publish a per-attempt `.gc/outputs/decomposition.md` substitute.

Before closing, read the launcher rig root from the workflow root bead's
`gc.work_dir`. If it names a per-step worktree without the check, walk to the
nearest ancestor containing `.gc/scripts/checks/build-artifact-valid.sh`. From
that launcher rig root, run the same canonical check used by the Ralph control:

```bash
GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Repair every validation error in the exact root artifact and rerun the command
until it passes.
Do not close based only on the artifact's existence or convoy readiness.

Do not invoke provider-native subagents or upstream plugin runtime commands.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) against schema `gc.build.decomposition.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
