Use the assigned Superpowers branch-finalization skill materialized for this agent.

Before writing the final report or closing this lane, materialize the canonical
implementation summary in the build artifact root. The workflow root must record
an absolute, existing path as
`gc.build.implementation_summary_path`, normally
`{{artifact_root}}/implementation-summary.md`. A per-item summary inside an
implementation worktree is not sufficient because that worktree is disposable.

Read the closed implementation source anchors and their recorded per-item
`gc.implementation.summary_path` values. If the root already points to a valid
`gc.build.implementation-summary.v1` artifact at the canonical path, preserve
it. Otherwise synthesize `implementation-summary.md` from those source anchors,
their summary paths, commits, changed files, verification evidence, and
remaining risks. The result must be Markdown with YAML front matter, use mapping
objects for `workflow`, `methodology`, `producer`, and `trace`, and declare:

- `schema: gc.build.implementation-summary.v1`
- the running Superpowers build workflow id and `formula: superpowers-build`
- `methodology: {pack: superpowers, name: superpowers-build}`
- a non-empty `trace.upstream` and matching `trace.coverage`

Its body must contain the exact `##` headings `Summary`, `Intended Behavior`,
`Changed Files`, `Verification`, and `Remaining Risks`, plus a Markdown coverage
table with `ID` and `Status` columns. Record the canonical absolute path before
writing the final report:

```sh
gc bd update "<workflow-root-id>" \
  --set-metadata "gc.build.implementation_summary_path=<absolute path>"
```

Do not create the final report or set `gc.outcome=pass` until the canonical
implementation summary exists and validates as
`gc.build.implementation-summary.v1`. Then confirm the final artifact paths,
test evidence, review state, residual risks, and publish readiness. Record the
build-base finalize outcome on the workflow root bead.

Do not invoke provider-native subagents or upstream plugin runtime commands.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.final_report_path` against schema `gc.build.final-report.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
