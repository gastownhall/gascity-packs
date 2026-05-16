---
description: Frontend-focused multi-agent pipeline (plan → architecture → review → frontend forge → devops → neurotic) with dev-tracker observing and verify-frontend-ux gating
argument-hint: <task description>
---

# /frontend-crew — Frontend Multi-Agent Crew Pipeline

Frontend variant of the crew pipeline. Use for any non-trivial UI work: new pages, route changes, component refactors, state-management changes, form work, accessibility work, styling overhauls, or anything that touches the rendered DOM. The pipeline does NOT clear without a real-browser UX verification on record.

## Task

$ARGUMENTS

## Pipeline Diagram

```
                                       ┌─────────────────────────────────────────────────────────┐
                                       │  dev-tracker (observer — interjects across all 6 steps) │
                                       └─────────────────────────────────────────────────────────┘
                                                                  │
                                                                  ▼
   ┌────────────┐    ┌──────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐    ┌──────────────────┐    ┌────────────────────────┐
   │ 1.         │ -> │ 2.               │ -> │ 3.                   │ -> │ 4.                  │ -> │ 5.               │ -> │ 6.                     │
   │ plan-agent │    │ architecture-    │    │ code-reviewer        │    │ frontend-developer  │    │ devops-engineer  │    │ neurotic-code-quality  │
   │ draft plan │    │ advisor          │    │ + api-designer       │    │ / react-typescript- │    │ deploy/infra +   │    │ + verify-frontend-ux   │
   │            │    │ reviews plan     │    │ (wire contract)      │    │ forge / yew-forge   │    │ bundle audit     │    │ FINAL — CLEAN or LOOP  │
   └────────────┘    └──────────────────┘    └──────────────────────┘    └─────────────────────┘    └──────────────────┘    └────────────────────────┘
        ▲                    │                         │                       │                        │                          │
        │                    ▼ FAIL                    ▼ FAIL                  ▼ FAIL                  ▼ FAIL                      ▼ FAIL
        └──────────────── targeted return path (architecture-advisor + code-reviewer scope the next pass) ──────────────────────────┘
```

The forge agent in step 4 is selected by stack:

| Stack | Forge agent |
|---|---|
| React + TypeScript SPA (general) | `frontend-developer` |
| React + TypeScript (component/hook focus) | `react-typescript-forge` or `react-forge` |
| Yew / WASM (Rust frontend) | `yew-forge` |

## FLOW

| Step | Agent | Action | Pass Requirements | Pass Action | Fail Condition | Fail Action |
|---|---|---|---|---|---|---|
| 1 | `plan-agent` | Map the affected routes, components, hooks, stores, forms, API calls. Draft an implementation plan with critical files, state-flow notes, and tradeoffs. | Plan exists, names every route/component/hook touched, identifies API consumption, calls out a11y and responsive concerns. | Hand to step 2. | Plan misses routes, ignores state flow, no a11y/responsive consideration. | Re-prompt `plan-agent` citing the missing pieces. |
| 2 | `architecture-advisor` | Review the plan for component boundaries, prop drilling vs context vs store, render-cost implications, dependency direction (UI → domain → infra). | No layer violations, state ownership is clear, render-cost budget acknowledged, side-effect placement is sound. | Hand plan + arch notes to step 3. | Component boundary violation, store/context misuse, render-cost regression risk, side effects in render. | Return to `plan-agent` with the deltas. |
| 3 | `code-reviewer` + `api-designer` | Pre-implementation review of the plan AND the backend↔frontend wire (paths, methods, request/response shapes, status codes, error envelope, auth flow). | Plan and wire contract are sound; frontend's expected shapes match backend's actual schema; error envelope handled. | Hand enriched plan to step 4. | Wire drift (path/method/shape mismatch), unhandled status codes, missing error envelope rendering. | Loop back to `plan-agent` or `architecture-advisor`. |
| 4 | Frontend forge agent | Implement the plan. Read `${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/frontend_guidelines.xml` (and `react_*` / `angular_*` as applicable) before writing. | TypeScript strict passes, ESLint clean (no `eslint-disable` without tracked reason), Prettier clean, all tests pass, no `console.log` / `debugger` shipped, no `any`/`unknown` hideouts, bundle build succeeds without warnings. | Hand artifact + diff to step 5. | Type errors, lint warnings, suppressions added, `any` introduced, leftover debug noise, bundle warning, broken story/test. | Forge iterates; after two failed iterations re-enter step 2/3. |
| 5 | `devops-engineer` | Audit bundle size delta, CDN/edge config, env-var wiring, CSP/security headers, source-map handling, cache invalidation, rollback. | No silent bundle-size regression, env vars match deployed config, CSP intact, source maps handled per policy, rollback path documented. | Hand to step 6. | Bundle bloat, missing env var in deployed env, CSP regression, broken cache key, no rollback. | Return to step 4 with findings; architectural root cause → step 2. |
| 6 | `neurotic-code-quality` **AND** `verify-frontend-ux` skill | (a) Hypersensitive zero-tolerance audit of code, build, deployed-vs-source skew, and backend↔frontend wire integrity. (b) `verify-frontend-ux` drives a real browser against every changed/affected page — clicks every interactive element, exercises every form, verifies console + network are clean, screenshots saved. | `neurotic-code-quality` verdict = **CLEAN**. `verify-frontend-ux` report = **SHIPPABLE**. Both required. | Pipeline complete. | Either verdict is **NOT CLEAN** / **NOT SHIPPABLE** / **UNVERIFIED**. | Return ONLY the failing slice to `architecture-advisor` + `code-reviewer` for a **targeted** next pass — never a broad restart. Re-enter step 4 with that narrowed scope. Repeat until both verdicts pass. |

`dev-tracker` observes all 6 steps and interjects on: a11y omission, responsive omission, secrets in client bundle, untested page, claim of "works" without browser evidence.

## Execution Rules

- **No solo execution.** Any non-trivial frontend change MUST run this pipeline.
- **Read frontend XML guidelines before writing.** Authoritative: `${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/frontend_guidelines.xml` (+ `react_*`, `angular_*` as applicable).
- **`verify-frontend-ux` is non-negotiable.** Tests, builds, type-checks, and curl checks DO NOT substitute. Real browser, real interactions, screenshots saved to `<project>/.scratch/ux-verify/<timestamp>/`.
- **Backend↔frontend wire parity is part of the audit.** `neurotic-code-quality` cross-checks deployed backend behavior against the frontend's expectations.
- **Zero `any`, zero suppressions, zero leftover debug.** Step 4 does not pass otherwise.
- **Targeted retries on step-6 failure.** Do NOT broad-restart — narrow the slice via steps 2 + 3, then re-enter step 4.
- **Determinate language only** in reports.

## Begin

Start at step 1. Spawn `plan-agent` with the task. Honor the FLOW table at every checkpoint. Report the final verdict only after step 6 returns CLEAN **and** `verify-frontend-ux` returns SHIPPABLE.
