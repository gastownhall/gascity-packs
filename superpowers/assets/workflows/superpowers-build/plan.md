Use the assigned Superpowers writing-plans skill materialized for this agent.

Write a plan artifact from the requirements output. Include enough implementation sequencing for build-base plan-review and decompose to proceed.

Write Markdown with YAML front matter, not a stock Superpowers plan by itself
and not JSON. Use mapping objects for nested front matter.
The artifact's first line must be `---`; close the front matter with a second line containing
exactly `---` before the Markdown body. Its top-level YAML shape must be:

- `schema: gc.build.plan.v1`
- `workflow: {id: <workflow-root-id>, formula: <root-workflow-formula>}`
- `methodology: {pack: superpowers, name: writing-plans}`
- `producer: {formula: superpowers-build, stage: plan, attempt: <positive integer>}`
- Set `producer.attempt` to this stage's current positive `gc.attempt`; a retry
  must update the canonical artifact to the retry's attempt before validation.
- Use `status: draft` before plan approval. The plan-review lane changes it to
  `status: approved`; do not invent lifecycle values such as `ready`.
- `trace: {upstream: [...], coverage: [...]}`

Every `trace.upstream[]` mapping must contain a path and a scheme-qualified
hash such as `bead:<id>`, `git:<revision>`, or `sha256:<digest>`. Do not put
requirements or design paths directly under `trace`. If an upstream entry
names IDs, include each ID once in `trace.coverage` and in a Markdown table
with matching `ID` and `Status` columns. Use schema coverage statuses such as
`covered`, `deferred`, or `out_of_scope`. Every non-`covered` coverage entry
must have a non-empty `rationale`.

Use these required second-level sections in this exact order:

- `## Summary`
- `## Current System`
- `## Proposed Implementation`
- `## Non-Goals`
- `## Verification`

Put all `### Task N` implementation sections under
`## Proposed Implementation` so the document satisfies both the Gas City
artifact schema and the stock Superpowers task format.

Read and write the exact artifact path from workflow root metadata
`gc.build.plan_path` (fallback `gc.var.plan_path`). Do not substitute a
per-attempt plan path.

Scoping invariant: the Superpowers build lifecycle phases are already being
executed by this formula. Do not write `prepare`, `requirements`, `plan`,
`plan-review`, `decompose`, `implement`, `summarize-implementation`, `review`,
`finalize`, or `publish` as `### Task N` implementation sections. Describe the
lifecycle in prose or traceability tables only.

Only `### Task N` sections are decomposed into implementation beads. Each
`### Task N` section must describe downstream source work for the original
input task or convoy member: files to modify, behavior to implement, tests to
write or run, and acceptance criteria. For the build fixture, the plan should
produce a single implementation task for `slugger.py` / `slugify()` unless the
approved requirements identify additional source-code work.

Before closing, read the launcher rig root from the workflow root bead's
`gc.work_dir`. If it names a per-step worktree without the check, walk to the
nearest ancestor containing `.gc/scripts/checks/build-artifact-valid.sh`. From
that launcher rig root, run the same canonical check used by the Ralph control:

```bash
GC_BEAD_ID="$CLAIMED_BEAD_ID" <launcher-rig>/.gc/scripts/checks/build-artifact-valid.sh
```

Repair every validation error in the exact root artifact and rerun the command
until it passes.
Do not close based only on the plan's existence or review status.

Do not invoke provider-native subagents or upstream plugin runtime commands.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.plan_path` (fallback `gc.var.plan_path`) against schema `gc.build.plan.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
