# gc magi status

Report the contents of `state.json` and the open bd beads tagged `pack:magi`. Reconciles orphaned `inflight.json` sentinels as the first action.

## Usage

```
gc magi status [flags]
```

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `--target <name>` | filters state.json `installs.<target>` view | all | Limits output to one target. |
| `--json` | switches the renderer to machine-readable JSON | off | Emits raw state JSON plus the bd open-bead list as a single document. |
| `--no-bd` | suppresses `bd list` / `bd ready` subprocess calls | off | Reads state.json only. |

## What it reports

- `state.json` from `${GC_CITY_PATH}/.gc/runtime/packs/magi/state.json`
- `bd list --label pack:magi --status open` (when bd is available)
- `bd ready --label pack:magi` (when bd is available)
- Orphan-reconciliation outcomes (closed `inflight.json` sentinels)

When bd is unavailable, the renderer marks `bd_available=false` and the output is degraded to state.json only.

## Example

```
gc magi status
gc magi status --target claude
gc magi status --json
```

## bd note

Status does not create new beads. It reads existing ones via `bd_show` and `bd_list_pack` (non-mutating). `--no-bd` skips even the reads.
