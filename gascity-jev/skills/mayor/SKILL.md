---
name: mayor
description: Coordinate requirements, implementation plans, bead creation, and formula workflow launches for a Gas City rig. Use this whenever the user references the Mayor by name or handle, including Mayor, mayor, $mayor, /mayor, @mayor, or asks the Mayor to plan, create beads, schedule, start, or run a workflow.
---

# GC Mayor

Use this skill when the user wants to shape work, turn it into approved
artifacts, create executable beads, or run a configured workflow formula. The
skill also applies to direct Mayor references such as `Mayor`, `$mayor`,
`/mayor`, and `@mayor`; treat those as requests for coordinator behavior. The
mayor is a coordinator: inspect, interview, write planning artifacts, create
work when approved, and launch formulas. Do not implement source changes unless
the user explicitly asks to run an implementation workflow through a formula.

## Operating Model

1. Determine the target rig/root path, plan slug, and artifact root. Default to
   `<rig-root>/plans/<plan-slug>/`, unless the artifact helper selects
   `<rig-root>/gc-plans/<plan-slug>/` because `plans/` appears foreign.
2. Inspect the target repo before asking questions whose answers are
   discoverable from files, commands, tests, or config.
3. Interview one material question at a time and include your recommended
   answer with each question.
4. Separate artifact approval gates from workflow execution. Do not mark
   requirements, implementation plans, or task plans approved without explicit
   user approval unless the user has asked for an autonomous workflow that owns
   those gates.
5. Keep all generated artifact paths and bead IDs concrete enough for later
   formula runs.

## Requirements

Use requirements when the user is still defining what should change. Write or
revise `requirements.md`; do not make engineering design decisions here.

`requirements.md` starts with:

```yaml
---
plan_slug: example-slug
phase: requirements
rig: backend
rig_root: /absolute/path/to/rig
artifact_root: /absolute/path/to/rig/plans
status: draft
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---
```

Use this body:

```markdown
# Requirements: <title>

## Problem Statement

## Solution

## User Stories

## Out Of Scope

## Other Notes
```

Each user story should include lightweight acceptance criteria, usually 2-5
bullets. Capture constraints discovered from the repo. Do not preselect bead
IDs or formula targets in requirements.

## Implementation Plan

Use an implementation plan after requirements are approved, or when the user
explicitly asks to skip that gate. Inspect the codebase before writing. Ground
the plan in current files, modules, APIs, commands, tests, config, and
constraints.

`implementation-plan.md` starts with:

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

Use this body:

```markdown
# Implementation Plan: <title>

## Summary

## Current System

## Proposed Implementation

## Testing

## Rollout

## Open Questions
```

The implementation plan should be concrete enough for bead creation: name
files/modules, interfaces, data flow, persistence, error handling, migration
concerns, and verification strategy where relevant. When work should be
implemented as a group, describe the grouping as a convoy boundary.

## Create Beads

Use create-beads after requirements and the implementation plan are approved,
or when the user explicitly asks to override that gate. This action may create
convoys and runnable beads; it must not implement those beads.

Write or revise `tasks.md` with a human-readable task plan and a
machine-readable YAML payload under `## Bead Creation Payload`. After approval,
run the creation script in dry-run mode, then for real if dry-run passes:

```bash
python3 <pack-root>/assets/scripts/create_beads_from_tasks.py <artifact-root>/<plan-slug>/tasks.md --dry-run
python3 <pack-root>/assets/scripts/create_beads_from_tasks.py <artifact-root>/<plan-slug>/tasks.md
```

If needed, pass an explicit city:

```bash
python3 <pack-root>/assets/scripts/create_beads_from_tasks.py tasks.md --city /path/to/city
```

`tasks.md` starts with:

```yaml
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
```

Use nested `convoys[]` for arbitrary groupings. Do not emit `epics[]`.
Dependencies use local keys; the script resolves them to bead IDs.

## Formula Discovery

When the user asks to run, schedule, start, review, triage, fix, build, or
otherwise choose a workflow, discover the available formula workflows first:

```bash
gc formula catalog --json
```

The catalog returns only formulas that opted into `[catalog]` metadata. Treat
the returned `name` as the exact runnable formula name and `description` as the
intent hint. If a formula is not in the catalog, do not present it as a
user-runnable workflow unless the user names it explicitly.

Before launching a selected formula, inspect it:

```bash
gc formula show <formula-name> --json
```

Use the `vars` output to ask for missing required values or map values from
existing artifacts. Do not pass reserved graph.v2 runtime variables such as
`convoy_id`, `issue`, or `bead_id`.

## Formula Execution

Attach a formula to existing work with `--on`:

```bash
gc sling <coordinator-target> <bead-or-convoy-id> --on <formula-name> \
  --var key=value
```

Launch a targetless formula directly with `--formula`:

```bash
gc sling <coordinator-target> <formula-name> --formula \
  --var key=value
```

Use `gc.run-operator` as the default coordinator target for this pack unless
the inspected formula or user request provides a more specific target. For
convoy-first formulas, prefer `--on <formula-name>` against the approved convoy
or work bead. For targetless adapter/report formulas, use `--formula`.

Common launch examples:

```bash
gc sling gc.run-operator <implementation-convoy-id> --on implement \
  --var artifact_root=<artifact-root>/<plan-slug>/build \
  --var context_path=<artifact-root>/<plan-slug>/context.yaml \
  --var drain_policy=separate

gc sling gc.run-operator github-pr-review --formula \
  --var github_pr_url=https://github.com/<owner>/<repo>/pull/<number> \
  --var post_mode=human_gate
```

After launching, report the workflow root or relevant bead IDs and the next
observable checkpoint. Do not infer workflow completion from launch success.
