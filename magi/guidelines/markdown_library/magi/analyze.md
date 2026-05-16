---
ignore_list:
  - "node_modules"
  - "__pycache__"
  - "dist"
  - "build"
  - "target"
  - "venv"
  - ".venv"
  - "tmp"
  - "work"
  - "scratch"
  - ".git"
  - ".idea"
  - ".vscode"
source_sha256_idempotency: true
lm_studio_required: true
default_model: "qwen/qwen3-coder-next"
default_lm_url: "http://localhost:1234"
default_context: 32768
output_filename: "_DIRECTORY_OVERVIEW.md"
---

# Analyze — Project Walk Rules

`magi_analyze.py` loads this file at startup. It wraps `project_analyzer/analyze_project.sh` and enforces the constants above.

## Traversal

Bottom-up. The analyzer visits leaf directories first and writes `_DIRECTORY_OVERVIEW.md` in each, then ascends. Parent overviews reference child overviews. The positional argument is an absolute path to the project root.

Relative paths fail at parse time. The orchestrator validates `Path(arg).is_absolute()` and raises `CLIError` on failure. The underlying script never sees magi-only flags.

## Ignore list

The analyzer skips every directory whose basename matches an entry in `ignore_list` above. Additional patterns may be appended via `--blocks-on` at the orchestrator layer; the underlying script reads only the built-in list.

## Idempotency

The analyzer keys each generated overview on the SHA-256 of the directory's source contents. Unchanged directories are skipped on re-run. `--force` (orchestrator) → `PROJECT_ANALYZER_FORCE=1` (script) regenerates every overview regardless of source hash.

This is independent of magi's bead-level idempotency. The analyzer's source-hash cache lives in the analyzer's own work tree; magi's `IDEMPOTENT_WINDOW_SECONDS` window applies only to bd-level bead reuse.

## LM Studio prerequisite

The analyzer probes `${PROJECT_ANALYZER_LM_URL}/api/v1/models` with a 30-second max-time curl. HTTP 200 is required. Any other response (including connect-refused) causes the script to exit non-zero before any file is written.

When LM Studio is on a non-default host or port, set `PROJECT_ANALYZER_LM_URL` via the `--lm-url` flag. When LM Studio requires a bearer token, set `LM_API_TOKEN` via the `--api-token` flag.

## Model defaults

`default_model` is loaded when the analyzer starts. The model context length is `default_context`. Both override via `--model` and `--context`.

## Argv hygiene

`magi_analyze.py` parses with `argparse.ArgumentParser(allow_abbrev=False)`, validates the project path, and execs:

```
subprocess.run(
    [str(analyze_sh), str(project_path)],
    env={**os.environ, **translated_env},
    check=False,
)
```

No `*sys.argv[1:]` splat. No `shell=True`. The subprocess never sees magi flag names.
