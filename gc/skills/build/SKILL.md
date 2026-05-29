---
name: build
description: Run the full GC planning-to-implementation workflow for one work item.
---

# GC Build

Use this skill when the user wants the pack to take a work item from rough
requirements through design, decomposition, implementation, gap-analysis,
review/fix loops, and an optional publish step.

## Workflow

1. Create or update `requirements.md` using `gc.gather-requirements`. Build starts with no
   required context beyond the user's request.
2. Stop for explicit human approval of requirements.
3. Create or update `implementation-plan.md` using `gc.plan-implementation`.
4. Stop for explicit human approval of design.
5. Create or update `tasks.md` using `gc.create-beads`, then create the initial
   implementation convoy.
6. Stop for explicit human approval of the task plan/start gate.
7. Write `context.yaml` with freeform context entries for requirements, design,
   tasks, and any generated implementation notes. Each entry has only `name`,
   `path`, and `description`.
8. Launch `build-run` against the approved implementation convoy. The durable
   run performs implement, gap-analysis/fix, review/fix, final reporting, and
   optional publish.

## Artifact Layout

Default to:

```text
<rig-root>/plans/<plan-slug>/
  requirements.md
  implementation-plan.md
  tasks.md
  context.yaml
  build/
    final-report.md
```

`build-run` owns durable loop state under `build/`. It must write a
`final-report.md` for success, failure, unavailable prerequisites, or recovery
needed states.

## Launch Contract

The approved initial implementation target is a convoy. Launch `build-run` with
the reserved graph.v2 target supplied by core and pass the context bundle path:

```sh
gc sling <coordinator-target> build-run --formula \
  --target <initial-convoy-id> \
  --var artifact_root=<artifact-root>/<plan-slug> \
  --var context_path=<artifact-root>/<plan-slug>/context.yaml \
  --var drain_policy=separate
```

`drain_policy` defaults to `separate`. Use `same-session` only when the user
explicitly requested preserved shared conversational context and the target
convoy is safe to execute as a single lane.
