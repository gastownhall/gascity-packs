---
description: Rust-focused multi-agent pipeline (plan → architecture → review → rust-forge → devops → neurotic) with dev-tracker as continuous observer
argument-hint: <task description>
---

# /rust-crew — Rust Multi-Agent Crew Pipeline

Rust-specific variant of the full-stack crew. Use for any non-trivial Rust work: multi-file changes, architectural shifts, async/sync boundary work, FFI, unsafe blocks, performance-critical paths, or anything bigger than a one-line fix. Solo execution is reserved for genuinely tiny edits.

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
   │ plan-agent │    │ architecture-    │    │ code-reviewer        │    │ rust-forge  │    │ devops-engineer  │    │ neurotic-code-quality  │
   │ draft plan │    │ advisor          │    │ (+ performance-      │    │ implements  │    │ deploy/infra     │    │ FINAL hypersensitive   │
   │            │    │ reviews plan     │    │  optimizer when hot) │    │             │    │ audit            │    │ pass — CLEAN or LOOP   │
   └────────────┘    └──────────────────┘    └──────────────────────┘    └─────────────┘    └──────────────────┘    └────────────────────────┘
        ▲                    │                         │                       │                    │                          │
        │                    ▼ FAIL                    ▼ FAIL                  ▼ FAIL              ▼ FAIL                      ▼ FAIL
        └──────────────── targeted return path (architecture-advisor + code-reviewer scope the next pass) ──────────────────────┘
```

`api-designer` joins step 3 when an HTTP/gRPC/RPC surface is in scope. `performance-optimizer` joins step 3 when the change is on a hot path (sync primitives, allocators, async runtime tuning, query layers, render loops).

## FLOW

| Step | Agent | Action | Pass Requirements | Pass Action | Fail Condition | Fail Action |
|---|---|---|---|---|---|---|
| 1 | `plan-agent` | Explore the crate(s), trait/impl topology, async runtime usage, error types, feature flags. Draft an implementation plan with critical files and tradeoffs. | Plan exists, identifies impacted crates, calls out trait/impl ripple, identifies error-type strategy, notes any `unsafe` introduction. | Hand to step 2. | Plan misses crate boundaries, error model, async coloring, or unsafe scope. | Re-prompt `plan-agent` citing the missing pieces. |
| 2 | `architecture-advisor` | Review for crate layering, module boundaries, dependency direction, feature-flag hygiene, public-API surface stability. | No layer violations; public API changes are intentional and documented; feature flags do not split-brain. | Hand plan + arch notes to step 3. | Crate cycles, leaked internals, feature-flag split-brain, accidental public API growth. | Return to `plan-agent` with the deltas. |
| 3 | `code-reviewer` (+ `api-designer` for wire surfaces, + `performance-optimizer` on hot paths) | Pre-implementation review of plan, error envelopes, perf budget. | Plan + contracts + perf expectations are sound; review checklist covered. | Hand enriched plan to step 4. | Gaps in error model, ambiguous Result/Option strategy, perf concerns, missing tests/benches. | Loop back to step 1 or 2 (whichever owns the gap). |
| 4 | `rust-forge` | Implement the plan. Read `${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/rust_guidelines.xml` first. Atomic edits. | `cargo fmt --check`, `cargo clippy --all-targets --all-features -- -D warnings`, `cargo build --all-targets`, `cargo test --all-targets`, `cargo doc --no-deps` — all clean. No `unwrap()` outside tests, no `expect()` without context, no `#[allow(...)]` without a tracked reason, no `unsafe` without a SAFETY comment. | Hand artifact + diff to step 5. | Any clippy warning, doc warning, test failure, suppressed lint without justification, `unwrap`/`expect` in production paths, missing SAFETY comment. | `rust-forge` iterates on the specific failures. After two failed iterations, re-enter step 2/3 for re-scoping. |
| 5 | `devops-engineer` | Audit CI matrix, MSRV, target triples, container build, binary size, observability, rollback. | CI green across the matrix, MSRV honored, container/binary builds clean, telemetry hooks present, rollback path documented. | Hand to step 6. | CI breakage on any target, MSRV violation, missing env var, container regression, no rollback. | Return to step 4 with findings; architectural root cause → step 2. |
| 6 | `neurotic-code-quality` | Final hypersensitive pass on backend code, frontend (if any), the wire between them, AND the deployed system if deployed. | Verdict = **CLEAN** across every applicable channel. | Pipeline complete. | Verdict = **NOT CLEAN** or **UNVERIFIED** on any channel. | Return ONLY the failing slice to `architecture-advisor` + `code-reviewer` for a **targeted** next pass. Re-enter at step 4 with that narrowed scope. Repeat until CLEAN. |

`dev-tracker` observes all 6 steps and interjects on scope drift, missing tests/benches, unsafe creep, secrets exposure, or deploy-without-evidence.

## Execution Rules

- **No solo execution.** Multi-file Rust work, architectural shifts, anything > one-line fix MUST go through this pipeline.
- **Read the Rust XML guideline before writing.** Authoritative source: `${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/rust_guidelines.xml`.
- **Zero clippy warnings, zero doc warnings, zero test failures.** Step 4 does not pass otherwise.
- **`unsafe` requires SAFETY comments and step-2 sign-off.** Adding `unsafe` mid-step-4 reopens step 2.
- **Parallel where independent.** Step 3's `code-reviewer` / `api-designer` / `performance-optimizer` calls run concurrently.
- **Targeted retries on step-6 failure.** Do NOT restart the whole pipeline on `neurotic-code-quality` failure — narrow the slice via steps 2 + 3, then re-enter step 4.
- **Frontend (if any) is UNVERIFIED until `verify-frontend-ux` has driven a real browser.**
- **Determinate language only** in reports.

## Begin

Start at step 1. Spawn `plan-agent` with the task. Honor the FLOW table at every checkpoint. Report the final verdict only after step 6 returns CLEAN.
