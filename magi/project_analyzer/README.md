# project_analyzer

Generates a `_DIRECTORY_OVERVIEW.md` for every directory in a target project,
bottom-up, by sending the contents of each directory to a local LM Studio
server. Output files use a fixed structure that lets other LLMs navigate
large projects without reading every file.

## What it does

1. Walks a target project bottom-up.
2. For every directory, runs `tree` (with a strict ignore list) to produce a
   pruned listing.
3. Reads the immediate files in that directory (text-only, size-capped) and
   any `_DIRECTORY_OVERVIEW.md` files written by previous iterations of
   child directories.
4. Sends everything to LM Studio (`POST /api/v1/chat`) with a prompt that
   forces a fixed Markdown structure.
5. Writes `<dir>/_DIRECTORY_OVERVIEW.md` for that directory.
6. Repeats until it reaches the project root.

Leaf directories receive deep, symbol-by-symbol detail. Higher-level
directories receive a synthesis that points at child overviews instead of
duplicating their content.

## Usage

```bash
./analyze_project.sh /absolute/path/to/your/project
```

That is the only public entry point. The wrapper:

- Validates the argument (must be an absolute path to an existing directory).
- Verifies/installs `python3`, `tree`, `jq`, `curl` (Homebrew on macOS,
  apt/dnf on Linux).
- Creates a project-local `.venv/`, installs `pydantic>=2`.
- Verifies that LM Studio is reachable and the requested model is present.
- Loads the model.
- Invokes the Python engine which walks the project and writes overviews.

## Configuration

All values are environment variables. None are required.

| Variable                  | Default                       | Purpose                                                       |
|---------------------------|-------------------------------|---------------------------------------------------------------|
| `LM_API_TOKEN`            | empty                         | Bearer token for LM Studio if API auth is enabled.            |
| `PROJECT_ANALYZER_MODEL`  | `qwen/qwen3-coder-next`       | Model key to load.                                            |
| `PROJECT_ANALYZER_LM_URL` | `http://localhost:1234`       | LM Studio base URL.                                           |
| `PROJECT_ANALYZER_FORCE`  | `0`                           | Set to `1` to regenerate even when the source hash matches.   |
| `PROJECT_ANALYZER_CONTEXT`| `32768`                       | Context length for the model load and per-request.            |

## Output

Every directory under the target project receives a file named
`_DIRECTORY_OVERVIEW.md`. Each file begins with a fixed provenance header:

```markdown
# Directory Overview: `<relative-path>`

<!-- project_analyzer:generated -->
<!-- generated_at=<ISO timestamp> -->
<!-- model=<model key> -->
<!-- input_tokens=... output_tokens=... tokens_per_second=... -->
<!-- project_analyzer:source-sha256=<64-hex digest> -->
```

Followed by a fixed section structure:

- Leaf directories: `## Purpose`, `## Files`, `## How to use this directory`.
- Inner directories: `## Purpose`, `## Files in this directory`,
  `## Subdirectories`, `## How this subtree fits together`.

The `source-sha256` line is hashed over filenames + sizes + mtimes of the
files and child overviews supplied for that directory. On the next run, if
the hash matches, the directory is skipped (idempotent). Set
`PROJECT_ANALYZER_FORCE=1` to bypass.

## Ignore list

The `tree` listing and the file walk both skip a fixed set of patterns:
junk dirs (`node_modules`, `__pycache__`, `dist`, `build`, `target`,
`venv`, `.venv`, `tmp`, `work`, `scratch`, `.git`, `.idea`, `.vscode`,
caches), macOS junk, and binary files (images, archives, executables).
Files matching `_*` and `*.log` and `*.tmp` are also dropped.

## Logs

Every run writes two log files into `logs/`:

- `wrapper_<timestamp>.log` — wrapper's bootstrap log (preflight, venv,
  LM Studio reachability, engine exit code, overview count).
- `engine_<basename>_<timestamp>.log` — engine's per-directory progress
  log (model loads, prompt sizes, elapsed times, token stats, failures).

Both are append-only, deterministic, and persistent.

## Dependencies

- macOS: Homebrew autoinstalls `tree`, `jq`, `curl` if missing.
- Linux: `apt-get` or `dnf` is used to autoinstall the same.
- Python 3.10+ is required (for `str | None` syntax). The wrapper expects
  `python3` on `PATH`.
- LM Studio must be running locally and serving the configured model.
  Start the server with `lms server start` and confirm the model is
  downloaded with `lms ls`.

## Files

- `analyze_project.sh` — the analyzer wrapper. Single positional argument is
  the project root. Generates `_DIRECTORY_OVERVIEW.md` per directory.
- `_analyzer.py` — the analyzer Python engine. Stdlib + Pydantic v2.
- `improve_project_analysis.sh` — the improver wrapper. Single positional
  argument is the project root. Runs after the analyzer. Generates
  `_IMPROVEMENTS.md` per directory and a project-wide
  `_PROJECT_IMPROVEMENT_BACKLOG.md`.
- `_improver.py` — the improver Python engine. Three-model pipeline
  (`nvidia/nemotron-3-nano-omni` → `nvidia/nemotron-3-super` →
  `minimax/minimax-m2.7`). Stdlib + Pydantic v2.
- `LM_STUDIO_API.md` — vendored copy of the LM Studio REST API reference.
- `CHANGELOG.md` — change log.
- `.venv/` — autocreated virtual environment.
- `logs/` — per-run logs.
- `.work/` — scratch space (LM Studio probe bodies, improver draft staging
  per run id).

## Improver tool

`improve_project_analysis.sh` is the second tool in the pipeline. It runs
**after** `analyze_project.sh` and consumes the `_DIRECTORY_OVERVIEW.md`
files plus the underlying source. It produces:

- `<dir>/_IMPROVEMENTS.md` per directory — concrete, source-anchored,
  severity-tagged improvement findings (Critical / High / Medium / Low),
  each with `Where` / `Why` / `How` / `Effort` / `Confidence`.
- `<project>/_PROJECT_IMPROVEMENT_BACKLOG.md` at the project root — a
  cross-directory synthesis: top-10 highest-leverage items, cross-cutting
  themes, quick wins (high impact × low effort), long-term refactors, and
  full severity-ordered findings index with anchors back to per-directory
  files.

Pipeline (per directory): a draft model produces a first pass, a stronger
verifier model prunes false positives and tightens citations, drafts are
staged on disk so Phase B can be re-run alone with `PROJECT_ANALYZER_RESUME=1`.
A final aggregator model reads every per-directory file and emits the
project backlog.

### Improver configuration

| Variable                            | Default                          | Purpose                                                       |
|-------------------------------------|----------------------------------|---------------------------------------------------------------|
| `PROJECT_ANALYZER_DRAFT_MODEL`      | `nvidia/nemotron-3-nano-omni`    | Phase A model.                                                |
| `PROJECT_ANALYZER_VERIFY_MODEL`     | `nvidia/nemotron-3-super`        | Phase B model.                                                |
| `PROJECT_ANALYZER_AGGREGATE_MODEL`  | `minimax/minimax-m2.7`           | Phase C model (project backlog).                              |
| `PROJECT_ANALYZER_FORCE`            | `0`                              | `1` regenerates even when source hash matches.                |
| `PROJECT_ANALYZER_SKIP_AGGREGATE`   | `0`                              | `1` skips Phase C.                                            |
| `PROJECT_ANALYZER_ONLY_AGGREGATE`   | `0`                              | `1` skips Phases A and B (only aggregate).                    |
| `PROJECT_ANALYZER_RESUME`           | `0`                              | `1` reuses the latest run's drafts; skips Phase A.            |

### Model lifecycle

The improver respects pre-loaded models. It checks `loaded_instances`
on `GET /api/v1/models` first. If a requested model already has a loaded
instance, it reuses that instance and never calls `/load`. If it loads a
model itself, it tracks the instance and unloads only that one at the
end of its phase. Instances pre-loaded by the operator are preserved
bit-for-bit across the run.

## Idempotency

Re-running the analyzer over an unchanged project is cheap: every
directory whose source hash is unchanged is skipped. Modifying any file
in a directory invalidates that directory's hash and triggers regeneration
on the next run. Modifying a child directory's `_DIRECTORY_OVERVIEW.md`
also invalidates the parent's hash, so summaries stay in sync with their
sources.
