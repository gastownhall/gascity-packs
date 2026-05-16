---
phases: ["draft", "verify", "aggregate"]
default_models:
  draft: "nvidia/nemotron-3-nano-omni"
  verify: "nvidia/nemotron-3-super"
  aggregate: "minimax/minimax-m2.7"
model_preload_preserved: true
resume_supported: true
default_lm_url: "http://localhost:1234"
default_context: 32768
per_dir_output: "_IMPROVEMENTS.md"
project_output: "_PROJECT_IMPROVEMENT_BACKLOG.md"
---

# Improve — Three-Model Pipeline Rules

`magi_improve.py` loads this file at startup. It wraps `project_analyzer/improve_project_analysis.sh` and enforces the constants above.

## Prerequisite

The project must already contain `_DIRECTORY_OVERVIEW.md` files from a prior `gc magi analyze` run. The improvement engine reads those files; it does not regenerate them.

## Phases

Each phase corresponds to a model in `default_models`:

1. **draft** — generates `_IMPROVEMENTS.md` in every directory from the analyze output
2. **verify** — re-reads each draft, raises issues the draft missed, rewrites the file
3. **aggregate** — reads every `_IMPROVEMENTS.md`, writes `_PROJECT_IMPROVEMENT_BACKLOG.md` at the project root

All three models load into LM Studio at pipeline start. The engine dispatches per-pass to the correct model. Model preload state is preserved across resume so weights are not re-loaded.

## Scope controls

- `--skip-aggregate` → `PROJECT_ANALYZER_SKIP_AGGREGATE=1` — runs per-dir draft + verify; skips the project-level aggregate.
- `--only-aggregate` → `PROJECT_ANALYZER_ONLY_AGGREGATE=1` — skips per-dir phases; reads existing `_IMPROVEMENTS.md` files and writes the backlog.

The two flags are mutually exclusive at the orchestrator layer; passing both fails at parse time.

## Resume semantics

`--resume` → `PROJECT_ANALYZER_RESUME=1` continues a prior run. The engine reads the resume state in the analyzer's work tree, restarts at the next unfinished directory, and reuses the preloaded models. Resume is safe to invoke multiple times; the engine is internally idempotent.

## Argv hygiene

Same contract as analyze: positional absolute path only, all flag-to-env translation happens at the orchestrator layer, `subprocess.run(..., check=False)`.

## Failure mode

Any phase failure exits the underlying script with non-zero rc. The orchestrator propagates the rc verbatim. The bd bead closes with `outcome:<rc>`. `--resume` on the next run picks up at the failed directory.
