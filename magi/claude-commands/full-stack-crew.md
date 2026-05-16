---
description: Multi-agent pipeline (plan → architecture → review → forge → devops → neurotic) with dev-tracker as continuous observer
argument-hint: <task description>
---

# /full-stack-crew — Multi-Agent Crew Pipeline

Execute the requested task as a **TEAM** of specialized agents — never solo. Each step is a checkpoint with explicit pass/fail criteria. The pipeline does not advance past a failing checkpoint; it returns to the responsible agent with targeted feedback. `dev-tracker` runs as a continuous observer across all steps and interjects when it sees drift.

## Task

$ARGUMENTS

## Pipeline Diagram

```
                                       ┌─────────────────────────────────────────────────────────┐
                                       │  dev-tracker (observer — interjects across all 6 steps) │
                                       └─────────────────────────────────────────────────────────┘
                                                                  │
                                                                  ▼
   ┌────────────┐    ┌──────────────────┐    ┌──────────────────────┐    ┌─────────────┐    ┌──────────────────┐    ┌────────────────────────┐
   │ 1.         │ -> │ 2.               │ -> │ 3.                   │ -> │ 4.          │ -> │ 5.               │ -> │ 6.                     │
   │ plan-agent │    │ architecture-    │    │ code-reviewer        │    │ <forge>     │    │ devops-engineer  │    │ neurotic-code-quality  │
   │ draft plan │    │ advisor          │    │ (+ api-designer)     │    │ implements  │    │ deploy/infra     │    │ FINAL hypersensitive   │
   │            │    │ reviews plan     │    │ reviews plan + APIs  │    │             │    │ audit            │    │ pass — CLEAN or LOOP   │
   └────────────┘    └──────────────────┘    └──────────────────────┘    └─────────────┘    └──────────────────┘    └────────────────────────┘
        ▲                    │                         │                       │                    │                          │
        │                    ▼ FAIL                    ▼ FAIL                  ▼ FAIL              ▼ FAIL                      ▼ FAIL
        └──────────────── targeted return path (architecture-advisor + code-reviewer scope the next pass) ──────────────────────┘
```

The forge agent in step 4 is selected by file type:

| File / language touched | Forge agent |
|---|---|
| Rust | `rust-forge` |
| Bash / shell | `bashforge-script-generator` (gen) + `bash-script-enforcer` (review) |
| TypeScript / React / SPA | `frontend-developer` or `react-typescript-forge` |
| Yew / WASM | `yew-forge` |
| Python | `python-forge` |
| C# / .NET | `csharp-forge` |
| Java / Maven | `java-forge` / `maven-forge` |
| Database / SQL | `database-architect` |
| Docs | `documentation-writer` |

Run independent agent calls in parallel where the pipeline allows (e.g. step 3 may call `code-reviewer` and `api-designer` concurrently).

## FLOW

| Step | Agent | Action | Pass Requirements | Pass Action | Fail Condition | Fail Action |
|---|---|---|---|---|---|---|
| 1 | `plan-agent` | Read the task, explore the codebase, draft a step-by-step implementation plan with critical file list and tradeoffs. | Plan exists, is sequenced, names the files and modules in scope, identifies dependencies, calls out risks. | Hand plan to step 2. | Plan is missing, vague, generic, or omits files/risks. | Re-prompt `plan-agent` citing the missing pieces; do not advance. |
| 2 | `architecture-advisor` | Review the plan for layering, dependency direction, coupling, boundary integrity, configuration management, and scalability. | Plan aligns with project architecture; no boundary violations; dependency direction sound; magic values and duplication called out. | Hand plan + arch notes to step 3. | Architectural concerns (layer violation, coupling, duplication, missing config seam, scope creep). | Return to `plan-agent` with the specific arch deltas; iterate until step 2 passes. |
| 3 | `code-reviewer` (+ `api-designer` when an API contract is in scope) | Pre-implementation review of the plan + arch notes. `api-designer` validates any new/changed endpoints, schemas, error envelopes. | Plan + APIs are sound; contracts are versioned and consistent; review checklist covered (correctness, security, testability). | Hand enriched plan to step 4. | Plan or contract gaps, security holes, missing tests, ambiguous error model. | Loop back to `plan-agent` or `architecture-advisor` (whichever owns the gap). Do not advance. |
| 4 | Forge agent(s) — chosen from the table above | Implement the plan. Read the applicable XML guideline before writing. Atomic edits. Linter, formatter, type-checker, build, tests must each pass clean. | Code compiles/builds with **zero warnings**, tests pass, formatter clean, type-checker clean, no suppressions, no TODOs. | Hand artifact + diff to step 5. | Build/test failure, warnings emitted, suppressions added, scope creep, partial implementation. | Forge agent iterates with the specific failures. After two failed iterations, re-enter step 2/3 for re-scoping. |
| 5 | `devops-engineer` | Audit the change for deployability, CI/CD impact, container/infra impact, secrets/env handling, observability, and rollback. | CI passes, no infra regression, secrets and env vars correctly wired, observability hooks present, rollback path documented. | Hand to step 6. | CI breaks, secrets leak, missing env var, no rollback, container/infra regression. | Return to step 4 with devops findings; if root cause is architectural, return to step 2. |
| 6 | `neurotic-code-quality` | Hypersensitive zero-tolerance final pass: warnings, suppressions, swallowed errors, dead code, magic values, contract drift, deployed-vs-source skew, backend↔frontend wire integrity. Defers frontend UX to the `verify-frontend-ux` skill. | Verdict = **CLEAN** across every applicable channel (backend local, frontend local, wire, deployed backend, deployed frontend). | Pipeline complete — report to user. | Verdict = **NOT CLEAN** or **UNVERIFIED** on any channel. | Return ONLY the failing slice to `architecture-advisor` + `code-reviewer` to scope a **targeted** next pass — not a broad restart. Re-enter at step 4 with that narrowed scope. Repeat until step 6 = CLEAN. |

`dev-tracker` runs in parallel across all 6 steps. It does not gate the pipeline but interjects when it sees: scope drift, anti-patterns, missing tests, secrets, frontend tested without browser, or deploy claimed without evidence. Its interjections are inputs to whichever step is currently active.

## Execution Rules

- **No solo execution.** Every step calls the named agent via the Task tool. If a step is skipped, the pipeline restarts.
- **Parallel where independent.** Step 3's `code-reviewer` and `api-designer` calls run in one message with two Task tool uses. Same applies to multi-language forge work in step 4.
- **Fail closed.** A failing checkpoint never advances. The pipeline either returns to the owning agent or escalates to architecture/review for re-scoping.
- **Targeted retries on step-6 failure.** Do NOT restart the whole pipeline on a `neurotic-code-quality` failure — `architecture-advisor` + `code-reviewer` scope the narrowest fix and the forge agent re-implements only that slice.
- **Frontend UX is non-negotiable.** Any frontend change is UNVERIFIED until the `verify-frontend-ux` skill has driven a real browser. `neurotic-code-quality` will refuse to clear without it.
- **Read guidelines before code.** Step 4's forge agent MUST read `${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/<lang>.xml` before writing.
- **Determinate language only** in all reports: `does`, `is`, `will`, `fails` — never `should`, `could`, `might`.

## Begin

Start at step 1. Spawn `plan-agent` with the task. Continue through the pipeline, honoring the FLOW table at every checkpoint. Report the final verdict only after step 6 returns CLEAN.
