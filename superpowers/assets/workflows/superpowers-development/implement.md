Inspect the Superpowers implementation task.

Resolve the source anchor with the same rules as the inherited worktree setup,
read its `work_dir`, and switch to that worktree before reading or editing
source files. Read the approved requirements, approved plan, decomposition
artifact, and this task bead. The task bead describes the work unit only; the
drained Superpowers implementation workflow supplies the execution procedure.

Use the installed `executing-plans`, `test-driven-development`, and
`using-git-worktrees` skills as guidance for this task. Confirm the task is
small enough to implement independently, identify the first test behavior to
drive, and write a compact task context note for the following implementation
steps.

Resolve the inner workflow root and exact source anchor before selecting the
per-item implementation summary. If `gc.implementation.summary_path` is blank,
use `<WORKTREE>/implementation-summary.md`; otherwise require the recorded
absolute path to be inside `WORKTREE`. Record that same absolute path on the
workflow root, this implement step, and the source anchor.

Create or update that file as a valid
`gc.build.implementation-summary.v1` Markdown artifact. Its front matter must
identify this workflow and Superpowers methodology, trace the exact source
anchor as `path: beads/<source-anchor-id>` with
`hash: bead:<source-anchor-id>`, and use schema-valid coverage. Include the
required `## Summary`, `## Intended Behavior`, `## Changed Files`,
`## Verification`, and `## Remaining Risks` sections. The later implementation
lanes update this same file; never create an attempt-local substitute.

Do not edit source files in the launcher checkout. Do not invoke
provider-native subagents or upstream plugin runtime commands.

Artifact validation: this step is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the summary recorded at `gc.implementation.summary_path` (fallbacks `gc.build.implementation_summary_path`, then `gc.var.summary_path`) against schema `gc.build.implementation-summary.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the summary in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the summary.
