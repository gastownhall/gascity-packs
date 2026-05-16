# magi/gemini

Pack-built installer for the Gemini CLI enforcement bridge. Targets `~/.gemini/` by default; override via `GEMINI_HOME` or `gc magi install --target gemini --home <path>`.

## What gets installed

| Path | Source | Purpose |
|---|---|---|
| `<home>/policies/enforcement.toml` | `gemini/harness/policies/enforcement.toml` | Policy ruleset the gemini-hook bridge reads at runtime |
| `<home>/enforcement/bin/gemini-hook.sh` | `gemini/harness/enforcement/bin/gemini-hook.sh` | Hook bridge invoked by Gemini CLI on pre/post-tool events |
| `<home>/AGENTS.md` | `gemini/harness/AGENTS.md` | Gemini-side agent guidance |
| `<pack-root>/.env` | shared magi configuration | Install-time env values for every target |
| `<home>_backup-YYYYMMDD-HHMMSS/` | created on every install | Backup of pre-install contents |

The installer is idempotent. Re-running with the same flags reproduces the same tree. Re-running with new flag values produces a new backup.

## Hook bridge

`gemini-hook.sh` is invoked by Gemini CLI for tool-use events. The bridge forwards the event payload to:

1. The local enforcement ruleset at `<home>/policies/enforcement.toml` for hard-deny rules.
2. The optional LM Studio reviewer (when `INSTALL_LM_STUDIO=1`) at `http://${LM_STUDIO_HOST}:${LM_STUDIO_PORT}/v1/chat/completions` for soft-review.

The bridge exits 0 (allow), 1 (block with reason), or 2 (warn). Gemini CLI consumes the exit code per its hook protocol.

## Env vars

| Var | Default | Effect |
|---|---|---|
| `GEMINI_HOME` | `~/.gemini` | Target install root |
| `INSTALL_GEMINI_HOOKS` | `1` | Install the hook bridge entries in `<home>/settings.json` |
| `INSTALL_LM_STUDIO` | `0` | Enable the LM Studio reviewer |
| `LM_STUDIO_HOST` | `localhost` | LM Studio host |
| `LM_STUDIO_PORT` | `1234` | LM Studio port |
| `LM_STUDIO_MODEL` | none | Reviewer model name |
| `GEMINI_TURN_CONTENT_LIMIT` | none | Per-turn content cap forwarded to the hook bridge |

## Logs

`<home>/enforcement/logs/gemini-hook.log` (created on first hook invocation, mode `0600`). The deploy log lives under `${GC_CITY_PATH}/.gc/runtime/packs/magi/logs/install-gemini-<utc>.log`.

## Idempotency

Same backup pattern as the codex deployer: `<home>_backup-YYYYMMDD-HHMMSS` next to the deployed home on every install. Backups survive uninstall.
