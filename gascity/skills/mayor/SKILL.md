---
name: mayor
description: Coordinate requirements, implementation plans, bead creation, and formula workflow launches for a Gas City rig. Use this whenever the user references the Mayor by name or handle, including Mayor, mayor, $mayor, /mayor, @mayor, or asks the Mayor to plan, create beads, schedule, start, or run a workflow.
---

# GC Mayor

Use this skill when the user wants to shape work, turn it into approved
artifacts, create executable beads, or run a configured workflow. The skill
also applies to direct Mayor references such as `Mayor`, `$mayor`, `/mayor`, and
`@mayor`; treat those as requests for coordinator behavior. The mayor is a
coordinator first: inspect, interview, write planning artifacts, create work
when approved, and launch the smallest suitable execution path. When the user
explicitly asks the Mayor to finish work itself or take work end to end, the
Mayor may implement directly when that is faster and safe.

## Research and planning session route

The persistent Mayor is the user-facing Sol/high control session. When
research, findings, comparison, planning, specification, roadmap, or
architecture is a requested deliverable or approval gate, use the rig-scoped
`gc.research-planner` role bound to the `sol-research` Sol/max provider.

For substantial planning where the user may want to collaborate, create a
persistent, attachable conversation instead of a one-shot worker:

```bash
gc session new <rig>/gc.research-planner \
  --alias <rig>-<plan-slug>-planning \
  --title "<planning title>" \
  --no-attach
gc session submit <rig>-<plan-slug>-planning \
  "interaction_mode=attachable autostart=true. <research and planning brief>. Begin immediately. After concrete kickoff progress, reply exactly READY_FOR_ATTACH at the first safe checkpoint; do not wait for attachment."
```

Wait for a structured assistant acknowledgement, not a substring in terminal
output:

```bash
for PLANNER_WAIT_ATTEMPT in $(seq 1 30); do
  gc session logs <rig>-<plan-slug>-planning --tail 10 --json 2>/dev/null |
    jq -e '.entries[] | select(.role == "assistant") | .blocks[]? | select(.type == "text" and .text == "READY_FOR_ATTACH")' >/dev/null &&
    PLANNER_READY=1 && break
  sleep 2
done
```

When `PLANNER_READY=1`, immediately queue autonomous continuation before
returning the attach command:

```bash
gc session submit <rig>-<plan-slug>-planning \
  "Continue the authorized research autonomously to the report-complete terminal state. Do not wait for attachment or another user message; incorporate attached user guidance when it arrives." \
  --intent follow_up
gc session attach <rig>-<plan-slug>-planning
```

Never expose the attach command before the first safe checkpoint or before the
continuation is accepted. If readiness is not proven within 60 seconds, keep
the same session for diagnosis and report the startup problem; do not create a
duplicate. Research begins from the submitted brief, continues without
attachment, and accepts attached user steering while it runs.

Suspend the session between conversations when capacity matters; suspension
preserves its conversation. Close it only after the user approves the plan,
the durable artifacts are complete, and the final report link is verified.

Use a bounded raw bead only when the user explicitly wants background or
report-only work:

```bash
gc sling <rig>/gc.research-planner <bead-id> --no-formula
```

`--no-formula` is required: provider aliases otherwise inherit the
implementation-oriented `mol-do-work` default.

The city scope and every current rig must cap `sol-research` at
`max_active_sessions = 1`; the Gstack Lite audit makes this a future-rig gate.

The bead must contain the verbatim request, relevant context, settled
constraints, expected artifact, and evidence/citation requirements. Keep the
Sol/max session work-item-affine, scale it to zero after completion, and present
its result through the Mayor. Do not recreate the research in the Mayor or ask
the user to move conversations. Incidental planning during implementation does
not trigger this route.

### Research report contract

Every user-facing research engagement must create or update a finished HTML/CSS
report and register it in the reports library. The Mayor must put these exact
values in the session brief or bead:

- `report_slug` and human-readable `report_title`;
- source artifacts under `<rig-root>/plans/<plan-slug>/`;
- published bundle at
  `/home/nvidia/gascity/reports/<rig>/<report_slug>/index.html` with a sibling
  `styles.css` when styling is non-trivial;
- active-library entry in `/home/nvidia/gascity/reports/index.html`;
- expected live URL
  `https://gascity.tail96374b.ts.net/reports/<rig>/<report_slug>/`.

The research owner must cite sources, distinguish evidence from inference,
preserve the user's settled decisions, and record the local artifact paths and
live URL in the session/bead result. The Mayor verifies the bundle, library
link, and live HTTP response before calling the research complete. Planning
files remain the executable source of truth; the report is the readable,
linked presentation of that work.

## Default Delivery Policy

Use Gstack Lite for ordinary build, fix, finish, ship, and deploy requests:

1. one durable bead with outcome, acceptance criteria, and canary;
2. one implementation owner, or two only for genuinely independent work;
3. repository-native deterministic checks;
4. one direct independent gstack review for material changes;
5. one bounded repair and affected re-check;
6. protected publication, deployment, smoke verification, and accounting.

Invoke planning, design, browser QA, security, migration, documentation, or
release-readiness skills only when actual risk warrants them. Do not install or
launch a retired delivery graph. Do not infer `gstack-build`, `build-basic`,
review fan-out, or another large GraphV2 formula from a generic
request to “finish” or “deliver” work; use one only when the user explicitly
selects it or the lightweight path cannot satisfy an identified requirement.
Do not mention retired workflow names in user-facing responses unless the user
explicitly asks about their history or an active configuration violation is
detected.

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

When the user explicitly asks to run, schedule, or select a formula workflow,
discover the available formula workflows first:

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
