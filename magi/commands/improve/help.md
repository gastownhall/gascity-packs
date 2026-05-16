# gc magi improve

Run the three-model pipeline (draft → verify → aggregate) over a previously-analyzed project. Per-directory writes `_IMPROVEMENTS.md`; a final aggregator pass writes `_PROJECT_IMPROVEMENT_BACKLOG.md` at the project root.

## Usage

```
gc magi improve /absolute/path/to/<project> [flags]
```

The project must already contain `_DIRECTORY_OVERVIEW.md` files from a prior `gc magi analyze` run.

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `--draft-model <name>` | `PROJECT_ANALYZER_DRAFT_MODEL` | `nvidia/nemotron-3-nano-omni` | Names the draft-pass model. |
| `--verify-model <name>` | `PROJECT_ANALYZER_VERIFY_MODEL` | `nvidia/nemotron-3-super` | Names the verify-pass model. |
| `--aggregate-model <name>` | `PROJECT_ANALYZER_AGGREGATE_MODEL` | `minimax/minimax-m2.7` | Names the aggregate-pass model. |
| `--lm-url <url>` | `PROJECT_ANALYZER_LM_URL` | `http://localhost:1234` | LM Studio base URL. |
| `--force` | `PROJECT_ANALYZER_FORCE=1` | off | Regenerates every improvement even when source SHA-256 matches. |
| `--context <n>` | `PROJECT_ANALYZER_CONTEXT` | `32768` | Model context length. |
| `--api-token <tok>` | `LM_API_TOKEN` | empty | Bearer token for LM Studio. |
| `--skip-aggregate` | `PROJECT_ANALYZER_SKIP_AGGREGATE=1` | off | Skips the final aggregator pass. |
| `--only-aggregate` | `PROJECT_ANALYZER_ONLY_AGGREGATE=1` | off | Runs only the aggregator pass over existing per-directory files. |
| `--resume` | `PROJECT_ANALYZER_RESUME=1` | off | Resumes a prior run; preloaded model state is preserved. |
| `--no-bd` | bypasses bd writes for this verb | off | Disables bd integration. |

## Underlying script contract

`project_analyzer/improve_project_analysis.sh` accepts only `<project_path>` as positional argv. Magi translates flags to `PROJECT_ANALYZER_*` env. The three models load into LM Studio at pipeline start; the engine dispatches per-pass to the correct model. Resume preserves the model preload so the second invocation does not re-load weights.

## Example

```
gc magi improve "${GC_CITY_PATH}"
gc magi improve "${GC_CITY_PATH}" --resume
gc magi improve "${GC_CITY_PATH}" --only-aggregate
gc magi improve "${GC_CITY_PATH}" --skip-aggregate --force
```

## bd note

Emits `pack:magi:improve` + `verb:improve` + `target:project` + `outcome:<rc>`. `--no-bd` disables this.
