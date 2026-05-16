# magi/openai

Pack-built installer for the LM Studio OpenAI-compatible configuration. Configures LM Studio so OpenAI-shaped clients (Claude Code via env, Codex CLI, project_analyzer) reach a single local endpoint.

## What gets installed

| Path | Source | Purpose |
|---|---|---|
| `<home>/config.toml` | `openai/templates/config.toml` | LM Studio runtime configuration (CORS, autoload model list, port) |
| `<home>/models.toml` | `openai/templates/models.toml` | Autoload-on-start model list |
| `<home>/shim/env.sh` | `openai/templates/env.sh` | Source-able file exporting `OPENAI_API_BASE` and `OPENAI_API_KEY` for client tools |
| `<home>/launchd/com.user.lmstudio.plist` | macOS only when `INSTALL_LAUNCHD=1` | Launches LM Studio at user login |
| `<home>_backup-YYYYMMDD-HHMMSS/` | created on every install | Backup of pre-install contents |

`<home>` defaults to `~/.config/lm-studio-magi/`. Override via `OPENAI_TARGET_HOME` or `gc magi install --target openai --home <path>`.

## OpenAI-compat shim

`shim/env.sh` exports:

```
export OPENAI_API_BASE="http://${LM_STUDIO_HOST}:${LM_STUDIO_PORT}/v1"
export OPENAI_API_KEY="${OPENAI_API_KEY:-lm-studio-local}"
```

Source this file before invoking any OpenAI-shaped client (project_analyzer, codex enforcement reviewer, ad-hoc curl):

```
source ~/.config/lm-studio-magi/shim/env.sh
gc magi analyze "${GC_CITY_PATH}"
```

`OPENAI_BASE_URL` (Codex CLI's preferred name) is set to the same value.

## Env vars

| Var | Default | Effect |
|---|---|---|
| `OPENAI_TARGET_HOME` | `~/.config/lm-studio-magi` | Target install root |
| `LM_STUDIO_HOST` | `localhost` | Bind host |
| `LM_STUDIO_PORT` | `1234` | Bind port |
| `LM_STUDIO_MODEL` | none | Default model name for clients that read this var |
| `LM_STUDIO_CONTEXT` | `32768` | Default context length for model preloads |
| `LM_STUDIO_AUTOLOAD_MODELS` | empty | Comma-separated model list to preload at LM Studio startup |
| `OPENAI_API_KEY` | `lm-studio-local` | Token returned by the shim; LM Studio ignores the value |
| `OPENAI_BASE_URL` | derived | Set automatically from host/port |

## launchd (macOS)

When `INSTALL_LAUNCHD=1` and the host is Darwin, the installer writes `<home>/launchd/com.user.lmstudio.plist` and runs `launchctl bootstrap gui/$(id -u) <plist>`. Linux ignores this flag; the installer prints a one-line note and continues.

## Logs

The deploy log lives under `${GC_CITY_PATH}/.gc/runtime/packs/magi/logs/install-openai-<utc>.log`. LM Studio's own logs follow its install location (typically `~/.cache/lm-studio/server-logs/`).

## Idempotency

Same backup pattern as the other deployers: `<home>_backup-YYYYMMDD-HHMMSS` on every install. The `config.toml` and `models.toml` are written from templates with the env values substituted; re-running with the same env values produces byte-identical files. Backups survive uninstall.
