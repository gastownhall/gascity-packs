# gc magi ready

List magi-tagged ready work via `bd ready --label pack:magi`. The label `pack:magi` is prepended automatically.

## Usage

```
gc magi ready [bd-ready-flags]
```

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `--limit <n>` | passed to `bd ready --limit <n>` | bd default | Caps the result count. |
| `--json` | passed to `bd ready --json` | off | Emits machine-readable output. |
| `--label <X>` | combined with implicit `pack:magi` as an AND filter | none | Adds a second label filter. Duplicates of `pack:magi` are deduplicated. |

## AND-filter caveat

`gc magi ready --label other:tag` resolves to `bd ready --label pack:magi --label other:tag`. bd interprets multiple `--label` flags as an AND filter: only beads carrying both labels surface. The wrapper warns when the user adds a label.

## Example

```
gc magi ready
gc magi ready --json
gc magi ready --limit 5
gc magi ready --label verb:install
```

## bd note

Read-only. Does not create beads. Fails fast when bd is absent.
