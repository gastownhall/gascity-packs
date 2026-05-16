# Changelog

All notable changes to project_analyzer.

## 2026-05-07

### Added
- `improve_project_analysis.sh` wrapper. Single positional argument is the
  project root. Sibling to `analyze_project.sh`. Verifies analyzer output is
  present, then invokes the improver engine through a three-model pipeline.
  Honours `PROJECT_ANALYZER_DRAFT_MODEL`, `PROJECT_ANALYZER_VERIFY_MODEL`,
  `PROJECT_ANALYZER_AGGREGATE_MODEL`, `PROJECT_ANALYZER_FORCE`,
  `PROJECT_ANALYZER_SKIP_AGGREGATE`, `PROJECT_ANALYZER_ONLY_AGGREGATE`,
  `PROJECT_ANALYZER_RESUME` environment variables. Logs to
  `logs/improver_wrapper_<ts>.log` and `logs/improver_engine_<basename>_<ts>.log`.
- `_improver.py` engine. Phase-based pipeline:
  1. **Draft** (`nvidia/nemotron-3-nano-omni`): emits a structured draft per
     directory containing source-anchored, severity-tagged improvement items.
     Drafts are persisted to `<project_analyzer>/.work/improver/<run_id>/<sha>.draft.md`
     plus a JSONL manifest, so Phase B can be re-run alone.
  2. **Verify** (`nvidia/nemotron-3-super`): receives the draft + the same
     source content. Skeptical disposition: drops false-positive findings
     (sshpass argument-quoting, internal-host StrictHostKeyChecking,
     deliberate hook-evasion patterns, severity inflation). Writes the final
     `<dir>/_IMPROVEMENTS.md`.
  3. **Aggregate** (`minimax/minimax-m2.7`): reads every `_IMPROVEMENTS.md`,
     identifies cross-cutting themes, produces severity-ordered
     `<project>/_PROJECT_IMPROVEMENT_BACKLOG.md` with file-anchored references
     to per-directory items.
- Proper LM Studio model lifecycle: ensure-loaded checks
  `loaded_instances` first; only issues `POST /api/v1/models/load` when no
  instance exists; only `POST /api/v1/models/unload` for instances this run
  loaded (preserves the operator's pre-loaded set bit-for-bit).
- `--resume` flag re-uses the most recent run's draft directory; lets
  Phase B run alone when Phase B fails or when iterating on the verify
  prompt without re-paying draft compute.
- `--skip-aggregate` and `--only-aggregate` flags control phase scope.
- Idempotency via per-directory source-content sha256 stamp on the
  `_IMPROVEMENTS.md` provenance header.
- Provenance headers on every output: `generated_at`, `draft_model`,
  `verify_model`, `aggregator_model`, draft/verify/aggregate token stats,
  `source-sha256`.
- System prompts tuned through smoke-testing on
  `claude_dist/harness/scripts/utilities`. Prompts explicitly enumerate
  common LLM false-positive classes for the verify pass to drop, and tell
  the draft pass not to flag them in the first place.

### Configuration
- Default models: draft `nvidia/nemotron-3-nano-omni`, verify
  `nvidia/nemotron-3-super`, aggregate `minimax/minimax-m2.7`.
- Per-file 12 KiB cap, per-directory aggregate 110 KiB cap, max 30 files.
- Output token caps: 8192 draft, 8192 verify, 12288 aggregate.

### Fixed
- Default `reasoning="off"` on chat requests; falls back to no-reasoning
  retry on model rejection; falls back to concatenated reasoning content
  when a model emits only `reasoning` items and no `message`.
- `LM_API_TOKEN` is exported (not `readonly` + prefix) so the engine
  inherits it through the wrapper.

## 2026-05-05

### Added
- `analyze_project.sh` wrapper. Single positional argument is the project root.
  Handles dependency detection (Homebrew on macOS, apt/dnf on Linux),
  Python venv creation, Pydantic v2 install, LM Studio reachability check,
  and engine invocation. Logs every step to `logs/wrapper_<ts>.log`.
- `_analyzer.py` engine. Walks the target project bottom-up. For every
  directory: runs `tree` with a strict ignore list, reads immediate files,
  reads child overviews, sends a structured prompt to LM Studio's
  `POST /api/v1/chat` endpoint, writes a standardized `_DIRECTORY_OVERVIEW.md`.
  Idempotent via per-directory source-content sha256 stamp.
- Standard output format. Every overview file carries a provenance header
  (`generated_at`, `model`, token stats, `source-sha256`) and a fixed
  section structure (leaf vs inner).
- `README.md` documenting usage, configuration, output format, and
  dependencies.
- `LM_STUDIO_API.md` vendored unchanged from the user-supplied reference.

### Configuration
- Defaults: `qwen/qwen3-coder-next`, `http://localhost:1234`, context 32768,
  per-file 6 KiB cap, per-directory aggregate cap 90 KiB, max 40 files per
  directory, max 40 child overviews per parent.

### Verified against
- Upstream `claude_dist/harness/scripts/utilities` (3 leaf files, 1 directory) — completed in 17.7s, output passed visual review.
- Upstream `claude_dist/harness/scripts` (2 directories: 1 leaf + 1 inner) — completed in 30s, inner overview correctly references child overview without duplicating detail.
- Full upstream `claude_dist` run (47 directories) in progress.

### Fixed
- Wrapper crashed at `engine.start` with `LM_API_TOKEN: readonly variable`
  because the variable was declared `readonly` and then prefixed onto the
  Python invocation. Replaced with explicit `export` before the `readonly`
  was applied.
