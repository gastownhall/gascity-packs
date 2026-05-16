# gc magi molecule

Run the magi bootstrap molecule: a parent bead with ordered children (`doctor → install → bootstrap-project → status → analyze`).

## Usage

```
gc magi molecule bootstrap [<project-path>] [flags]
gc magi molecule pour <formula-name> [flags]
gc magi molecule wisp <formula-name> [flags]
```

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `--target <name>` | passed to the `install` child step | `claude` | Names the install target. |
| `--project-path <abs>` | passed to the `bootstrap-project` and `analyze` child steps | required for `bootstrap` | Absolute path to a project root. |
| `--no-bd` | bypasses bd writes for this verb | off | Disables bd integration. |

## Subcommands

- `bootstrap` — creates parent bead, then 4 children via `bd_create` + `bd_dep`. Walks the chain via `bd ready`.
- `pour <name>` — hands off to `bd mol pour <name>` with the bundled formula proto.
- `wisp <name>` — hands off to `bd mol wisp <name>`.

## Failure semantics

On first child failure, the parent stays open with label `outcome:partial`. Remaining un-ready children are not auto-cancelled. The operator decides via `gc magi status` whether to re-run the failed child or close the molecule. Exit code matches the worst child rc.

## Example

```
gc magi molecule bootstrap "${GC_CITY_PATH}" --target claude
gc magi molecule pour mol-magi-bootstrap
gc magi molecule wisp mol-magi-bootstrap
```

## bd note

Emits `pack:magi:molecule` + `verb:molecule` parent bead; children carry `role:child`. The bundled formula is `formulas/mol-magi-bootstrap.formula.toml`.
