Write the Superpowers requirements spec from the approved design.

This lane maps stock Superpowers checklist items 6-7: write the durable design
doc/spec, then run the inline Spec self-review before any user/spec approval
gate can pass.

Re-resolve the actual request before writing the spec. When workflow root
metadata `gc.var.convoy_id` is present, read it as `<launch-convoy-id>`, run
`gc convoy status <launch-convoy-id> --json`, and treat every direct
launch-convoy member as a source target. Run `gc bd show <source-target-id> --json`
for each source and use its title, description, acceptance criteria, and
constraints as authoritative product scope. The approved design may elaborate
that scope but may not replace it.

There is one narrow context-only exception: when the workflow root formula is
exactly `superpowers-planning` and has no launch convoy, resolve
`gc.var.context_path`, require it to be an existing regular file, and use its
contents as the authoritative internal planning scope. Trace that exact path in
`trace.upstream` with the `sha256:` digest of its current bytes. Any other
missing, empty, ambiguous, or unreadable launch convoy must fail closed instead
of inventing requirements. A context path never replaces the launch convoy for
a real build root.

Trace every direct launch-convoy member exactly once using
`path: beads/<source-target-id>` and `hash: bead:<source-target-id>`. Do not
substitute the workflow root, expansion controls, convoy, or an empty context
file. This bead trace rule applies when a launch convoy exists; the internal
planning exception instead uses the exact context path and digest described
above. Preserve IDs declared by a source verbatim; do not attribute invented
IDs to a source that did not declare them.

Resolve the approved design candidate from workflow root metadata. Convert that
design into the normalized requirements artifact consumed by build-base. Include
the requested outcome, constraints, non-goals, accepted design, acceptance
criteria, testing expectations, risks, and any remaining questions.

The normalized artifact is Markdown with YAML front matter, not a stock
Superpowers design document and not JSON. Use mapping objects for nested front
matter. The artifact's first line must be `---`; close the front matter with a
second line containing exactly `---` before the Markdown body. Its top-level
YAML shape must be:

- `schema: gc.build.requirements.v1`
- `workflow: {id: <workflow-root-id>, formula: <root-workflow-formula>}`
- `methodology: {pack: superpowers, name: superpowers-brainstorming}`
- `producer: {formula: superpowers-brainstorming, stage: requirements, attempt: <positive integer>}`
- Use `status: draft` before written-spec approval. The approval lane changes
  it to `status: approved`; do not invent lifecycle values such as `ready`.
- `trace: {upstream: [...], coverage: [...]}`

Every `trace.upstream[]` mapping must contain a path and a scheme-qualified
hash such as `bead:<id>`, `git:<revision>`, or `sha256:<digest>`. If an upstream
entry names IDs, include every ID once in `trace.coverage` and in a Markdown
table with matching `ID` and `Status` columns. Use coverage statuses such as
`covered`, `deferred`, or `out_of_scope`; do not use artifact statuses such as
`approved` as coverage statuses. Every non-`covered` coverage entry must have a
non-empty `rationale`.

Use these required second-level sections in this exact order:

- `## Problem Statement`
- `## W6H`
- `## User Stories`
- `## Technical Stories`
- `## Behavior Requirements`
- `## Example Mapping`
- `## Acceptance Criteria`
- `## Out Of Scope`
- `## Open Questions`

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

Write or update the exact path from workflow root metadata
`gc.build.requirements_path` (fallback `gc.var.requirements_path`). Do not
substitute a per-attempt output path. If the target repo can safely mirror a design doc under
`docs/superpowers/specs/`, record that mirror path in the artifact, but do not
commit from this lane unless the routed bead explicitly asks for it.

Before closing, validate the normalized artifact directly. Read the launcher
rig root from the workflow root bead's `gc.work_dir`. If it names a per-step
worktree without the validator, walk to the nearest ancestor containing
`.gc/scripts/validate_build_artifact.py`. Run:

```text
python3 <launcher-rig>/.gc/scripts/validate_build_artifact.py --schema gc.build.requirements.v1 --path <requirements-artifact-path> --verify-absolute-upstreams --upstream-root <launcher-rig>
```

Repair every validation error in that exact root artifact and rerun this
command until it passes.
Do not mark the lane passed based only on file existence or written-spec
approval metadata.

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
