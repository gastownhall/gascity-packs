---
name: create-beads
description: Turn an approved requirements/implementation-plan pair into an approved bead plan and create the beads.
---

# GC Create Beads

Use this skill after `gc.gather-requirements` and `gc.plan-implementation` have approved artifacts. This is
a planning and task-creation skill: it may write `tasks.md` and create convoys
and runnable beads, but it must not implement those beads.

## Workflow

1. Confirm the target rig/root path, plan slug, and artifact root. Default to:
   `<rig-root>/plans/<plan-slug>/`.
2. Read `requirements.md` and `implementation-plan.md`. Refuse to proceed unless both are
   `approved`, unless the user explicitly overrides that gate.
3. Inspect the target codebase enough to validate task boundaries,
   dependencies, file ownership, and test strategy.
4. Draft `tasks.md` with a human-readable task plan and a machine-readable YAML
   payload under `## Bead Creation Payload`.
5. Interview the user one question at a time until the task plan is approved.
6. When approved, update `status: approved`, run the bead creation script in
   dry-run mode, then run it for real if dry-run passes.
7. After creation, ensure `tasks.md` records `status: created` and the
   `## Created Beads` mapping for both convoy heads and runnable beads.

## Artifact

`tasks.md` must begin with YAML front matter:

````yaml
---
plan_slug: example-slug
phase: tasks
rig: backend
rig_root: /absolute/path/to/rig
artifact_root: /absolute/path/to/rig/plans
requirements_file: /absolute/path/to/requirements.md
implementation_plan_file: /absolute/path/to/implementation-plan.md
status: draft
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---
````

Use this body structure:

````markdown
# Task Plan: <title>

## Summary

## Convoys

## Beads

## Dependency Graph

## Creation Notes

## Open Questions

## Bead Creation Payload

```yaml
target_rig: backend
labels:
  - plan:example-slug
convoys:
  - key: implementation
    title: Implement example
    description: Owns implementation work for this plan.
    target: feature/example
    metadata:
      gc.plan.phase: implementation
    convoys: []
    beads:
      - key: stable-local-key
        title: Short imperative title
        type: task
        priority: 2
        description: |
          Full implementation instructions.
        acceptance_criteria:
          - Concrete done condition.
        dependencies: []
        files: []
        verification: []
```
````

Use nested `convoys[]` for arbitrary groupings. Do not emit `epics[]`. A convoy
is a bead-backed grouping object, not a blocking dependency mechanism; express
blocking relationships against runnable children when they are precise.
`convoys[].dependencies` is allowed as shorthand only when the downstream roots
should depend on the upstream terminal runnable beads. Dependencies use local
keys; the script resolves them to bead IDs.

## Bead Creation

Use the pack script:

```bash
python3 <pack-root>/assets/scripts/create_beads_from_tasks.py <artifact-root>/<plan-slug>/tasks.md --dry-run
python3 <pack-root>/assets/scripts/create_beads_from_tasks.py <artifact-root>/<plan-slug>/tasks.md
```

If needed, pass an explicit city:

```bash
python3 <pack-root>/assets/scripts/create_beads_from_tasks.py tasks.md --city /path/to/city
```
