# gc magi analyze

Walk a project bottom-up and write `_DIRECTORY_OVERVIEW.md` into every directory using a local LM Studio server. Source files are idempotency-keyed on SHA-256; unchanged content is skipped.

## Usage

```
gc magi analyze /absolute/path/to/<project> [flags]
```

The positional path is required and must be absolute. Unknown magi flags fail at parse time and never reach the underlying script.

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `--model <name>` | `PROJECT_ANALYZER_MODEL` | `qwen/qwen3-coder-next` | Names the LM Studio model. |
| `--lm-url <url>` | `PROJECT_ANALYZER_LM_URL` | `http://localhost:1234` | LM Studio base URL. |
| `--force` | `PROJECT_ANALYZER_FORCE=1` | off | Regenerates every overview even when source SHA-256 matches. |
| `--context <n>` | `PROJECT_ANALYZER_CONTEXT` | `32768` | Model context length. |
| `--api-token <tok>` | `LM_API_TOKEN` | empty | Bearer token for LM Studio. |
| `--blocks-on <list>` | none — magi-only | empty | Names additional ignore-list patterns appended to the analyzer's built-in skip set. |
| `--no-bd` | bypasses bd writes for this verb | off | Disables bd integration. |

## Underlying script contract

`project_analyzer/analyze_project.sh` accepts only `<project_path>` as positional argv. Magi translates flags to `PROJECT_ANALYZER_*` env before exec and forwards no other argv. LM Studio at `<lm-url>/api/v1/models` must return HTTP 200 or the script exits non-zero.

Built-in ignore list: `node_modules`, `__pycache__`, `dist`, `build`, `target`, `venv`, `.venv`, `tmp`, `work`, `scratch`, `.git`, `.idea`, `.vscode`.

## Example

```
gc magi analyze "${GC_CITY_PATH}"
gc magi analyze "${GC_CITY_PATH}" --model qwen/qwen3-coder-next --lm-url http://localhost:1234
gc magi analyze "${GC_CITY_PATH}" --force --context 65536
```

## bd note

Emits `pack:magi:analyze` + `verb:analyze` + `target:project` + `outcome:<rc>`. The hook `hook_pre_analyze.py` probes LM Studio reachability on `bead.created`. `--no-bd` disables this.
