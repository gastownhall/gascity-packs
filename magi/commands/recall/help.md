# gc magi recall

Read a magi-namespaced key from `bd memories`. Keys are prefixed with `magi:` automatically.

## Usage

```
gc magi recall <key> [flags]
gc magi recall --list
```

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `<key>` | passed to `bd recall magi:<key>` | required unless `--list` | The unprefixed key. |
| `--list` | runs `bd memories --query magi` | off | Lists every magi-namespaced memory. |
| `--json` | switches the renderer to JSON | off | Emits raw memory bodies. |

## Underlying behavior

When the key is absent, the verb exits rc=2 and prints `not found: magi:<key>`. When bd is absent, rc=1 and `bd unavailable` is logged.

## Example

```
gc magi recall last-target
gc magi recall --list
gc magi recall design-note --json
```

## bd note

Read-only. Does not create or update beads.
