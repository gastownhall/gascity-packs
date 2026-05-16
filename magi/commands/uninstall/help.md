# gc magi uninstall

Remove a magi-deployed runtime. Defaults to a state-only uninstall (clears `state.json` records and closes open install beads); a full filesystem purge requires two flags.

## Usage

```
gc magi uninstall --target <claude|codex|gemini|openai|all> [flags]
```

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `--target <name>` | selects target dir from `TARGET_REGISTRY` | required | Names the runtime to uninstall. |
| `--yes` | confirmation gate | off | Confirms non-purge uninstall. Required for any state mutation. |
| `--dry-run` | none — magi-only | off | Logs the planned removals; performs no mutations. |
| `--really-purge` | combined with `--yes` triggers filesystem removal of the deployed home | off | Removes the target home directory (e.g. `~/.claude`). Two flags required: `--really-purge --yes`. |

## Underlying behavior

Uninstall consumes only magi state plus the deployed home directory:

- closes any open `pack:magi:install` beads for the target with the extra label `role:uninstall-closure`
- updates `state.json` `installs.<target>` to `installed=false`
- when `--really-purge --yes`: removes `<deployed-home>` and writes `last_uninstall_timestamp`

Deployer backups (e.g. `<deployed-home>_backup-YYYYMMDD-HHMMSS`) survive uninstall. Restore by renaming the backup back over the deployed home and running `gc magi status` to refresh state.

## Example

```
gc magi uninstall --target claude --dry-run
gc magi uninstall --target claude --yes
gc magi uninstall --target claude --really-purge --yes
```

## bd note

Emits `pack:magi:uninstall` + `verb:uninstall` + `target:<name>`. Closes prior install beads with `role:uninstall-closure` so `hook_post_install.py` skips them.
