# gc magi bootstrap-project

Wrap `${MAGI_UTILITIES_SOURCE}/setup_utilities.sh -y` against a project root. The script creates a `.utilities` symlink pointing at the per-user shared tree. Magi never vendors `.utilities/` content.

## Usage

```
gc magi bootstrap-project [<project-path>] [flags]
```

When `<project-path>` is omitted, the verb resolves `${GC_CITY_PATH}`.

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `--project-path <abs>` | positional argv to `setup_utilities.sh` | `${GC_CITY_PATH}` | Absolute path to the project root. |
| `--dry-run` | logs the planned invocation | off | Performs no mutations. |
| `--source <path>` | overrides `MAGI_UTILITIES_SOURCE` for this run | pack-root `.env` | Names the `.utilities/` source tree. |
| `--no-bd` | bypasses bd writes | off | Disables bd integration. |

## Underlying behavior

The verb resolves `${MAGI_UTILITIES_SOURCE}` from the pack-root `.env` or inherited environment and execs `${MAGI_UTILITIES_SOURCE}/setup_utilities.sh -y <project-path>`. On success it verifies that `<project-path>/.utilities` resolves to a symlink whose target is `${MAGI_UTILITIES_SOURCE}`.

When `MAGI_UTILITIES_SOURCE` is unresolved or `setup_utilities.sh` is missing, the verb fails with rc=1 and records the failure in `state.json`.

## Example

```
gc magi bootstrap-project "${GC_CITY_PATH}"
gc magi bootstrap-project --dry-run
MAGI_UTILITIES_SOURCE="/path/to/.utilities" gc magi bootstrap-project "${GC_CITY_PATH}"
```

## bd note

Emits `pack:magi:bootstrap-project` + `verb:bootstrap-project` + `target:project` + `outcome:<rc>`. `--no-bd` disables this.
