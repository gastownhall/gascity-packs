# gc magi remember

Persist a magi-namespaced key/value pair via `bd remember`. Keys are prefixed with `magi:` automatically.

## Usage

```
gc magi remember <key> <value> [flags]
```

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `<key>` | passed to `bd remember --key magi:<key>` | required | The unprefixed key. |
| `<value>` | passed to `bd remember --value <value>` | required | The value; secret-keyed values are redacted before write. |
| `--no-bd` | suppresses bd write; logs and exits 0 | off | Useful for diagnostics. |

## Underlying behavior

Values pass through `redact_secrets()` before bd subprocess invocation. Storing a value that matches a `SECRET_KEY_PATTERNS` entry writes `key=<redacted>` instead of the raw secret.

When bd is absent, the verb logs a single warning and exits 0.

## Example

```
gc magi remember last-target claude
gc magi remember design-note "magi unifies five deployers behind one verb"
```

## bd note

Writes `bd remember --key magi:<key>`. Recall via `gc magi recall <key>` or `bd memories --query magi`.
