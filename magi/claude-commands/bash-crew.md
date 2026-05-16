---
description: Bash-focused multi-agent pipeline (plan → architecture → review → bashforge → devops → neurotic) with dev-tracker observing
argument-hint: <task description>
---

# /bash-crew — Bash Multi-Agent Crew Pipeline

Bash variant of the crew pipeline. Use for any non-trivial shell scripting: deployment scripts, build pipelines, `.utilities/` automation, cross-platform install scripts, CI/CD glue, or anything bigger than a one-off command. Solo execution is reserved for trivial fixes.

## Task

$ARGUMENTS

## Pipeline Diagram

```
                                       ┌─────────────────────────────────────────────────────────┐
                                       │  dev-tracker (observer — interjects across all 6 steps) │
                                       └─────────────────────────────────────────────────────────┘
                                                                  │
                                                                  ▼
   ┌────────────┐    ┌──────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────┐    ┌────────────────────────┐
   │ 1.         │ -> │ 2.               │ -> │ 3.                   │ -> │ 4.                   │ -> │ 5.               │ -> │ 6.                     │
   │ plan-agent │    │ architecture-    │    │ code-reviewer        │    │ bashforge-script-    │    │ devops-engineer  │    │ neurotic-code-quality  │
   │ draft plan │    │ advisor          │    │ + bash-script-       │    │ generator            │    │ deploy/infra     │    │ FINAL — CLEAN or LOOP  │
   │            │    │ reviews plan     │    │ enforcer             │    │ implements           │    │ audit            │    │                        │
   └────────────┘    └──────────────────┘    └──────────────────────┘    └──────────────────────┘    └──────────────────┘    └────────────────────────┘
        ▲                    │                         │                          │                         │                          │
        │                    ▼ FAIL                    ▼ FAIL                     ▼ FAIL                   ▼ FAIL                      ▼ FAIL
        └──────────────── targeted return path (architecture-advisor + code-reviewer scope the next pass) ──────────────────────────────┘
```

`utilities-agent` joins step 2 and step 3 when the script lives in `.utilities/`. `bash-script-enforcer` rides shotgun in step 3 and again in step 4 to enforce the bash XML guideline as code is written.

## FLOW

| Step | Agent | Action | Pass Requirements | Pass Action | Fail Condition | Fail Action |
|---|---|---|---|---|---|---|
| 1 | `plan-agent` | Identify the script's purpose, target platforms (Darwin / Linux distros), service-manager assumptions, dependencies, idempotency requirements, and self-healing cascade. Draft a plan. | Plan exists, names target platforms, lists dependencies + install cascade, defines idempotency strategy, defines log path. | Hand to step 2. | Plan misses platforms, dependency cascade, idempotency, or logging. | Re-prompt `plan-agent` citing the missing pieces. |
| 2 | `architecture-advisor` (+ `utilities-agent` if `.utilities/`) | Review for portability, separation of concerns, function decomposition, configuration vs. code, no project-specific references in shared `.utilities/`. | Cross-platform, decomposed into named functions, no hardcoded paths/IPs/credentials, log path defined, exit-code policy defined. | Hand plan + arch notes to step 3. | Hardcoded values, monolithic body, project-specific code in `.utilities/`, missing platform branch. | Return to `plan-agent` with the deltas. |
| 3 | `code-reviewer` + `bash-script-enforcer` (+ `utilities-agent` if `.utilities/`) | Pre-implementation review of plan against `bash_guidelines.xml` and `automation_principles.xml`. | Plan honors XML guideline (shebang, strict mode, function naming, quoting, header block, color definitions, output formatting, self-healing cascade). | Hand enriched plan to step 4. | Guideline gaps, missing strict mode, missing self-healing, missing platform detection. | Loop back to step 1 or 2. |
| 4 | `bashforge-script-generator` | Implement the plan. Read `${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/bash_guidelines.xml` first. | `shellcheck -x -S style` clean, `shfmt -d` clean, script runs end-to-end without errors, runs a SECOND time idempotently, all variables quoted, no `2>/dev/null`, no `\| true` masking, no `head`/`tail`/`2>&1 \| tee`, no `/tmp` / `$TMPDIR` / `/var/folders`, no `bash -c` inline, log file written from inside the script. | Hand artifact + log to step 5. | Any shellcheck warning, formatter drift, runtime error, second-run failure, banned pattern present, missing log file. | Forge iterates on the specific failures. After two failed iterations, re-enter step 2/3. |
| 5 | `devops-engineer` | Audit cross-platform behavior on Darwin and at least one Linux variant, CI integration, secret handling (`${MAGI_PACK_DIR}/enforcement/env.remote` references only), exit-code propagation, observability via the script's log file. | Runs on Darwin + Linux, no hardcoded credentials, exit codes propagate, log file is durable, CI integration documented. | Hand to step 6. | Platform-specific failure, hardcoded creds, swallowed exit code, log not persisted. | Return to step 4 with findings; architectural root cause → step 2. |
| 6 | `neurotic-code-quality` | Final hypersensitive pass: warnings, suppressions, swallowed errors, banned patterns, idempotency, drift between source and any deployed copy of the script, and (if the script touches a deployed system) the deployed system's behavior. | Verdict = **CLEAN** across every applicable channel. | Pipeline complete. | Verdict = **NOT CLEAN** or **UNVERIFIED**. | Return ONLY the failing slice to `architecture-advisor` + `code-reviewer` for a **targeted** next pass. Re-enter step 4 with that narrowed scope. Repeat until CLEAN. |

`dev-tracker` observes all 6 steps and interjects on: hardcoded values, banned patterns being introduced, missing idempotency, manual-fix shortcuts that should live in the script.

## Execution Rules

- **No solo execution.** Any non-trivial bash work runs this pipeline.
- **Read the bash XML guideline before writing.** Authoritative: `${MAGI_PACK_DIR}/enforcement/guidelines/guideline_documents/xml/bash_guidelines.xml` plus `automation_principles.xml`.
- **Self-healing cascade is mandatory.** Every dependency requires an `ensure_*` / `install_*` function attempting Homebrew → apt/dnf/pacman/zypper → language installers → version managers → official sources before failing.
- **Idempotency is mandatory.** A second run on the same inputs MUST succeed without manual intervention.
- **Banned patterns stay banned.** No `2>/dev/null`, no `head`, no `tail`, no `2>&1 | tee`, no inline `bash -c`, no `/tmp` / `$TMPDIR` / `/var/folders`, no `--no-verify`, no `|| true` masking failure.
- **The script writes its own log.** No external `tee` wrappers — the script appends to its own log file from inside.
- **All variables quoted.** `"${var}"` always.
- **Credentials reference `${MAGI_PACK_DIR}/enforcement/env.remote`** by variable name; never hardcoded.
- **Targeted retries on step-6 failure.** Do NOT broad-restart — narrow the slice via steps 2 + 3, then re-enter step 4.
- **Determinate language only** in reports.

## Begin

Start at step 1. Spawn `plan-agent` with the task. Honor the FLOW table at every checkpoint. Report the final verdict only after step 6 returns CLEAN.
