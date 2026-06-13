---
name: decompose
description: Turn an approved requirements/design pair into LazyJJ-ready work beads.
---

# GC LazyJJ Decompose

Use this skill after `gc.plan` and `gc.design` have approved artifacts. This is
a planning and task-creation skill: it may write `tasks.md` and create
LazyJJ-ready beads, but it must not implement those beads.

## Workflow

1. Confirm the target rig/root path, plan slug, and artifact root. Default to:
   `<rig-root>/.gc/plans/<plan-slug>/`.
2. Read `requirements.md` and `design.md`. Refuse to proceed unless both are
   `approved`, unless the user explicitly overrides that gate.
3. Inspect the target codebase enough to validate task boundaries,
   dependencies, file ownership, and test strategy.
4. Draft `tasks.md` with a human-readable task plan and a machine-readable YAML
   payload under `## Bead Creation Payload`.
5. Interview the user one question at a time until the task plan is approved.
6. When approved, update `status: approved`, run the bead creation script in
   dry-run mode, then run it for real if dry-run passes.
7. After bead creation, ensure `tasks.md` records `status: created` and the
   `## Created Beads` mapping.

## Artifact

`tasks.md` must begin with YAML front matter:

````yaml
---
plan_slug: example-slug
phase: tasks
rig: backend
rig_root: /absolute/path/to/rig
artifact_root: /absolute/path/to/rig/.gc/plans
requirements_file: /absolute/path/to/requirements.md
design_file: /absolute/path/to/design.md
status: draft
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---
````

Use this body structure:

````markdown
# Task Plan: <title>

## Summary

## Epics

## Beads

## Dependency Graph

## Creation Notes

## Open Questions

## Bead Creation Payload

```yaml
target_rig: backend
labels:
  - plan:example-slug
epics: []
beads:
  - key: stable-local-key
    title: Short imperative title
    type: task
    priority: 2
    description: |
      Full implementation instructions for one focused LazyJJ stack.
    formula: mol-polecat-lazyjj-work
    acceptance_criteria:
      - Concrete done condition.
    dependencies: []
    files: []
    verification: []
```
````

Create epic entries only when a larger outcome naturally groups three or more
beads. Dependencies use local keys; the script resolves them to bead IDs.
Every implementation bead should target `formula: mol-polecat-lazyjj-work`
unless the bead is intentionally for a different LazyJJ tutorial workflow.

## Bead Creation

Use the pack script:

```bash
python3 <pack-root>/scripts/create_beads_from_tasks.py <artifact-root>/<plan-slug>/tasks.md --dry-run
python3 <pack-root>/scripts/create_beads_from_tasks.py <artifact-root>/<plan-slug>/tasks.md
```

If needed, pass an explicit city:

```bash
python3 <pack-root>/scripts/create_beads_from_tasks.py tasks.md --city /path/to/city
```
