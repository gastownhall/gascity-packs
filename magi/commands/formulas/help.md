# gc magi formulas

List, show, or cook the bd formulas bundled with this pack. Currently ships `mol-magi-bootstrap`.

## Usage

```
gc magi formulas list
gc magi formulas show <name>
gc magi formulas cook <name> [--var key=value ...]
```

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `<name>` | resolves to `formulas/<name>.formula.toml` | required for `show` and `cook` | Names a bundled formula. |
| `--var key=value` | forwarded to `bd mol pour <name> --var key=value` | empty | Sets a formula variable. |
| `--json` | switches the renderer to JSON | off | Emits raw formula TOML or cook output. |

## Behavior

- `list` — scans `formulas/*.formula.toml`; reports `name`, `version`, `description`.
- `show <name>` — pretty-prints the formula TOML plus its declared `[vars]`.
- `cook <name>` — instantiates the formula as a molecule via `bd mol pour <name>` and reports the resulting parent bead id.

## Example

```
gc magi formulas list
gc magi formulas show mol-magi-bootstrap
gc magi formulas cook mol-magi-bootstrap --var target=claude --var project_path="${GC_CITY_PATH}"
```

## bd note

`cook` writes a parent bead with `pack:magi:molecule` + `verb:molecule` + the formula name in the bead title. Read-only operations create no beads.
