Write the Superpowers requirements spec from the approved design.

This lane maps stock Superpowers checklist items 6-7: write the durable design
doc/spec, then run the inline Spec self-review before any user/spec approval
gate can pass.

Resolve the approved design candidate from workflow root metadata. Convert that
design into the normalized requirements artifact consumed by build-base. Include
the requested outcome, constraints, non-goals, accepted design, acceptance
criteria, testing expectations, risks, and any remaining questions.

The approved design candidate is the Gas City artifact for the stock design-doc state.
If the run can safely mirror that document into the target repository, use the
stock `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` location; otherwise
keep it under the workflow artifact root and record the artifact path for
traceability.

On repeated attempts, read the current requirements/spec artifact and the latest
feedback application summary before writing. Preserve previously accepted
review fixes and explicit user edits; update the artifact from the approved
design without clobbering loop feedback.

Run the stock Spec self-review before closing:

- Placeholder scan: remove `TBD`, `TODO`, incomplete sections, and vague
  requirements.
- Internal consistency: resolve contradictions between sections.
- Scope check: keep the spec focused enough for one implementation plan.
- Ambiguity check: make any two-way interpretation explicit.

Write or update the normalized requirements artifact path from workflow root
metadata. If the target repo can safely mirror a design doc under
`docs/superpowers/specs/`, record that mirror path in the artifact, but do not
commit from this lane unless the routed bead explicitly asks for it.

The requirements artifact is a Markdown build artifact validated against
`gc.build.requirements.v1`, not a freeform design doc. The file must start
with YAML front matter on its first line (`---`), and the front matter must
declare `schema: gc.build.requirements.v1`, the workflow id/formula, the
methodology pack/name, the producer formula/stage/attempt, `status`, and
`trace` with upstream and coverage entries. Use mapping objects, not dotted
keys or scalar shortcuts:

```yaml
---
schema: gc.build.requirements.v1
workflow:
  id: <workflow-root-id>
  formula: <workflow-root-formula>
methodology:
  pack: superpowers
  name: superpowers-brainstorming
producer:
  formula: superpowers-brainstorming
  stage: write-requirements-spec
  attempt: 1
status: approved
trace:
  upstream:
    - path: <approved design candidate path>
      hash: sha256:<digest>
      ids: [REQ-001]
  coverage:
    - id: REQ-001
      status: covered
---
```

- `trace.upstream[]` entries must include `path` and `hash`. For bead inputs,
  use `path: beads/<bead-id>` and `hash: bead:<bead-id>`.
- If an upstream entry lists `ids`, every listed id must appear exactly once in
  `trace.coverage` and in a Markdown coverage table with an `ID` column and a
  `Status` column whose ID/status pairs exactly match `trace.coverage`.
- Coverage statuses are not artifact statuses: use `covered`,
  `not_applicable`, `deferred`, `blocked`, `out_of_scope`, or `superseded`,
  never `approved`.
- Include these required sections as `##` headings, in this order: Problem Statement,
  W6H, User Stories, Technical Stories, Behavior Requirements, Example
  Mapping, Acceptance Criteria, Out Of Scope, and Open Questions.

When mirroring the spec under `docs/superpowers/specs/`, the mirror may omit
the front matter; the artifact recorded at `gc.build.requirements_path` must
keep it.

Before closing, update the exact claimed bead id with the lane metadata:

```bash
gc bd update "$CLAIMED_BEAD_ID" \
  --set-metadata 'gc.outcome=pass' \
  --set-metadata 'design_review.output_path=<requirements artifact path>' \
  --set-metadata 'design_review.self_review_passed=true'
gc bd close "$CLAIMED_BEAD_ID" --reason 'Superpowers requirements spec written and self-reviewed.'
```

Do not pass `--metadata` or `--set-metadata` to `gc bd close`. Do not set
`design_review.verdict`; the approval lane owns the loop verdict.

Do not invoke provider-native subagents or upstream plugin runtime commands.
This Gas City lane owns the written spec pass.
