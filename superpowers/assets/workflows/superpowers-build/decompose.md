Create the Superpowers implementation convoy from the approved plan.

Read the approved requirements artifact, the approved Superpowers plan, and any
existing decomposition artifact path. The plan may contain the stock
Superpowers task structure with checkbox steps for test writing, verification,
implementation, and commit. Treat those checkbox steps as execution procedure,
not as task-bead content.

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

Create or update the implementation convoy with those beads and dependency
edges. Record the implementation convoy ID on the workflow root bead as
`gc.input_convoy_id=<implementation-convoy-id>` with
`gc bd update <workflow-root-id> --set-metadata gc.input_convoy_id=<implementation-convoy-id>`.

Write a decomposition artifact that maps every plan task to its bead ID and
dependency edges. Close this step only after the decomposition artifact exists,
the workflow root bead has `gc.input_convoy_id`, and the implementation convoy
is ready for drain before closing.

Do not invoke provider-native subagents or upstream plugin runtime commands.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.decomposition_path` (fallback `gc.var.decomposition_path`) against schema `gc.build.decomposition.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
