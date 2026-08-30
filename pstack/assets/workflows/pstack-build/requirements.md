Use the built-in Gas City guided starter factory requirements flow.

Create the requirements artifact at the path recorded on the workflow root bead
as `gc.build.requirements_path` (fallback `gc.var.requirements_path`). The
artifact must be Markdown with YAML front matter, not JSON. Its front matter
must declare `schema: gc.build.requirements.v1`, the workflow id/formula, the
methodology pack/name, the producer formula/stage/attempt, `status`, and
`trace` with upstream and coverage entries. Include a Markdown coverage table
whose ID/status pairs exactly match `trace.coverage`.
The validator only recognizes a Markdown table with an `ID` column and a
`Status` column. Use this shape:

| ID | Status |
| --- | --- |
| REQ-001 | covered |

Use mapping objects for front matter; do not use scalar shortcuts such as
`workflow: build-basic`. The top-level YAML shape must be:

- `schema: gc.build.requirements.v1`
- `workflow: {id: <workflow-root-id>, formula: build-basic}`
- `methodology: {pack: gascity, name: build-basic}`
- `producer: {formula: build-basic, stage: requirements, attempt: <positive integer>}`
- `status: approved` or another schema-allowed status
- `trace: {upstream: [...], coverage: [...]}`

Trace front matter must use the validator shape exactly:

- `trace.upstream[]` entries must include `path` and `hash`; do not use
  `id`/`title`/`type` entries as the upstream shape.
- For bead inputs, use `path: beads/<bead-id>` and `hash: bead:<bead-id>`.
  For file or artifact inputs, use a repo-relative or artifact-relative path
  and a scheme-qualified hash such as `sha256:<digest>` or `git:<revision>`.
- If an upstream entry lists `ids`, every listed id must appear exactly once in
  `trace.coverage` and in the Markdown coverage table with the same status.
- Coverage statuses are not artifact statuses. Use `covered` for satisfied
  requirements; do not use `approved` in `trace.coverage[].status` or the
  Markdown coverage table.

Use the same expectations as the `generate-requirements` stage in the GitHub
issue fix workflow. Preserve the input target, normalize the artifact path, and
make the acceptance criteria specific enough for plan review.

Keep the artifact approachable for a first factory run. Include the required
schema sections:

- Problem Statement
- W6H
- User Stories
- Technical Stories
- Behavior Requirements
- Example Mapping
- Acceptance Criteria
- Out Of Scope
- Open Questions

Within those sections, make the goal, constraints, acceptance criteria,
non-goals, and open questions explicit.

If `interaction_mode` is interactive or the user is present, ask only the
minimum question needed to unblock the artifact. If the workflow is autonomous
or headless, record unresolved ambiguity in open questions instead of blocking
without a clear need.

Record the requirements path on the workflow root bead before closing. Use
`gc bd update "<workflow-root-id>" --set-metadata "gc.build.requirements_path=<absolute path>"`.
Do not use `gc bd update --metadata 'key=value'`; `--metadata` only accepts a JSON
object.
Before closing this step, set the claimed step outcome with
`gc bd update "<claimed-step-id>" --set-metadata "gc.outcome=pass"`, then close
with `gc bd close "<claimed-step-id>" --reason "<concise reason>"`. Do not pass
`--metadata` or `--set-metadata` to `gc bd close`.

Artifact validation: this stage is gated by `.gc/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.requirements_path` (fallback `gc.var.requirements_path`) against schema `gc.build.requirements.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.
