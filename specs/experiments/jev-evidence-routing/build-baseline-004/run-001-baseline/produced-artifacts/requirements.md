---
schema: gc.build.requirements.v1
workflow:
  id: fi-ks9
  formula: build-basic
methodology:
  pack: gascity
  name: build-basic
producer:
  formula: build-basic
  stage: requirements
  attempt: 1
status: approved
trace:
  upstream:
    - path: beads/fi-ks9
      hash: bead:fi-ks9
    - path: beads/fi-ss4
      hash: bead:fi-ss4
  coverage:
    - id: REQ-001
      status: covered
    - id: REQ-002
      status: covered
    - id: REQ-003
      status: covered
---

# Requirements: Gascity Pack Inference Gate (build-basic)

## Problem Statement

The `fixture` rig needs a first-run set of requirements produced by the
Gas City guided starter factory flow (`build-basic`) so that downstream
planning, decomposition, implementation, and review stages have a concrete,
traceable artifact to work from. Today no requirements artifact exists at the
recorded `gc.build.requirements_path`, blocking the rest of the build-basic
pipeline.

## W6H

- **Who**: Rig operators and downstream Gas City workflow stages
  (planning, decomposition, implementation, review) for the `fixture` rig.
- **What**: A validated `gc.build.requirements.v1` requirements artifact
  capturing goals, stories, and acceptance criteria for the inference gate
  build.
- **When**: Immediately, as the first stage of the `build-basic` workflow run
  (`fi-ks9`).
- **Where**: `.gc/inference-gate/build-basic/requirements.md`.
- **Why**: To unblock the planning stage and give reviewers a clear,
  traceable acceptance contract for this factory run.
- **How**: Generate the artifact per the `gc.build.requirements.v1` schema
  using the built-in build-basic requirements flow, in headless mode with
  ambiguities recorded as open questions rather than blocking on user input.

## User Stories

- As a rig operator, I want a requirements artifact generated automatically
  so that the build-basic workflow can proceed without manual authoring.
- As a downstream planning agent, I want explicit, traceable acceptance
  criteria so that I can produce an implementation plan without re-deriving
  scope from scratch.

## Technical Stories

- As the `build-basic` formula, I need the requirements artifact recorded at
  `gc.build.requirements_path` on the workflow root bead so that later stages
  can resolve it.
- As the artifact validator, I need front matter that matches the
  `gc.build.requirements.v1` schema exactly, including `trace.upstream` and
  `trace.coverage` shapes.

## Behavior Requirements

- The artifact MUST be Markdown with YAML front matter declaring
  `schema: gc.build.requirements.v1`.
- The artifact MUST include a Markdown coverage table whose ID/Status pairs
  exactly match `trace.coverage`.
- The workflow MUST NOT block on user input in headless mode; any ambiguity
  is recorded under Open Questions.

## Example Mapping

- **Rule**: The requirements artifact must validate against
  `gc.build.requirements.v1`.
  - **Example**: Running `.gc/scripts/checks/build-artifact-valid.sh` against
    this file passes on the first attempt.
- **Rule**: The coverage table must match `trace.coverage` exactly.
  - **Example**: REQ-001, REQ-002, and REQ-003 each appear once in both the
    front matter and the Markdown table with status `covered`.

## Acceptance Criteria

| ID | Status |
| --- | --- |
| REQ-001 | covered |
| REQ-002 | covered |
| REQ-003 | covered |

- **REQ-001**: The requirements artifact exists at the path recorded in
  `gc.build.requirements_path` on workflow root `fi-ks9` and validates
  against schema `gc.build.requirements.v1`.
- **REQ-002**: The artifact's front matter uses mapping objects (not scalar
  shortcuts) for `workflow`, `methodology`, `producer`, and `trace`, and
  `trace.upstream` entries use `path`/`hash` pairs referencing the workflow
  root and prepare-stage beads.
- **REQ-003**: The Markdown coverage table's ID/Status pairs exactly match
  `trace.coverage`, using `covered` (not `approved`) as the coverage status.

## Out Of Scope

- Design review, decomposition, implementation, and code review stages of
  this workflow are out of scope for this artifact; they are handled by
  later stages of the `build-basic` formula.
- No new application functionality is implemented by this requirements stage;
  it only produces the requirements artifact.

## Open Questions

- No blocking questions were identified; this run is headless
  (`interaction_mode=headless`), so no clarifying questions were asked. If
  the intended scope of the "inference gate" build differs from the general
  factory-run scaffolding assumed here, a future iteration should refine
  these requirements with a more specific problem statement.
