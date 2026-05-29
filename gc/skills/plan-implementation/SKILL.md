---
name: plan-implementation
description: Turn approved requirements into a repo-grounded implementation plan document.
---

# GC Plan Implementation

Use this skill after `gc.gather-requirements` has produced an approved `requirements.md`. This
is a planning-only skill: inspect code and write the design document, but do not
implement product/source changes.

## Workflow

1. Confirm the target rig/root path, plan slug, and artifact root. Default to:
   `<rig-root>/plans/<plan-slug>/`.
2. Read `requirements.md`. Refuse to proceed if its front matter status is not
   `approved`, unless the user explicitly overrides that gate.
3. Inspect the target codebase before writing the design. Ground the design in
   current files, modules, APIs, commands, tests, config, and constraints.
4. Interview the user one question at a time:
   - Provide your recommended answer with each question.
   - Ask only questions that materially affect the design.
   - Inspect the repository instead of asking when the answer is discoverable.
5. Write or overwrite `implementation-plan.md`.
6. Ask the user to review. When the user explicitly approves, update
   `status: approved`. Otherwise leave `status: draft` or `status: questions`.
7. For build-compatible designs, include the implementation context that later
   steps should carry forward. Build will turn those references into
   `context.yaml` entries with `name`, `path`, and `description`.

## Artifact

`implementation-plan.md` must begin with YAML front matter:

```yaml
---
plan_slug: example-slug
phase: implementation-plan
rig: backend
rig_root: /absolute/path/to/rig
artifact_root: /absolute/path/to/rig/plans
requirements_file: /absolute/path/to/requirements.md
status: draft
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---
```

Use this body structure:

```markdown
# Implementation Plan: <title>

## Summary

## Current System

## Proposed Design

## Testing

## Rollout

## Open Questions
```

The design should be concrete enough for decomposition: name files/modules,
interfaces, data flow, persistence, error handling, migration concerns, and
verification strategy where relevant. When work should be implemented as a
group, describe the grouping as a convoy boundary; do not introduce epics as a
separate task type.
