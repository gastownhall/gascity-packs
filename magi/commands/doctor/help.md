# gc magi doctor

Run every magi precondition check. Each check returns an exit code; the aggregator reports the worst.

## Usage

```
gc magi doctor [flags]
```

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `--json` | switches the renderer to machine-readable JSON | off | Emits a per-check JSON document with `name`, `rc`, `severity`, `note`. |
| `--no-bd` | suppresses the summary bead | off | Skips the aggregate `pack:magi:doctor` bead create. |

## Checks

| check | severity model |
|---|---|
| `deploy-prereqs` | fail when `jq`, `rsync`, `sed`, `awk`, `find`, or `chmod` is missing |
| `python` | fail when `python3` is missing or < 3.10 |
| `lmstudio` | warn-only; checks `http://${LM_STUDIO_HOST}:${LM_STUDIO_PORT}/v1/models` |
| `ssh` | fail only when `INSTALL_REMOTE_MCP=1`; otherwise warn |
| `launchd` | macOS requires `launchctl`; Linux returns 0 |
| `beads` | warn-only when `bd` is absent on PATH |
| `utilities` | warn-only when `${MAGI_UTILITIES_SOURCE}` is unresolved |

## Exit codes

- `0` — every check returned 0
- `1` — any check returned 1 (fail)
- `2` — at least one check returned 2 (warn), zero returned 1

## Example

```
gc magi doctor
gc magi doctor --json
```

## bd note

Emits `pack:magi:doctor` + `verb:doctor` + `outcome:<worst-rc>` as a single summary bead. `--no-bd` disables this.
