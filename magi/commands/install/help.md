# gc magi install

Install or update a magi target runtime. One verb covers five deployers: `claude`, `codex`, `gemini`, `openai`, and the meta-target `all` which iterates the registry.

## Usage

```
gc magi install --target <claude|codex|gemini|openai|all> [flags]
```

## Flags

| magi flag | underlying flag or env | default | effect |
|---|---|---|---|
| `--target <name>` | selects `<target>/deploy_*.sh` from `TARGET_REGISTRY` | required | Names the runtime to deploy. `all` iterates every registered target. |
| `--home <path>` | `--target=<path>` on `deploy_harness.sh` / `deploy_gemini.sh` / `deploy_openai.sh`; falls back to env `CODEX_HOME` / `GEMINI_HOME` / `OPENAI_TARGET_HOME` per target | per-target default home | Overrides the install root for the selected target. |
| `--dry-run` | `--dry-run` on the underlying deployer | off | Forwards the deployer's dry-run mode; zero filesystem mutations. |
| `--non-interactive` | `--non-interactive` on the underlying deployer | off | Never prompts; reads values from the pack-root `.env` or fails. |
| `--skip-prereqs` | `--skip-prereqs` on the underlying deployer | off | Skips the deployer's prereq probe. |
| `--bd-push` | `bd dolt push` after successful close | off | Triggers a federated push of the install bead. |
| `--no-bd` | bypasses `bd_create` / `bd_close` for this verb | off | Disables bd integration; state.json still updates. |
| `--skip-utilities` | suppresses `${MAGI_UTILITIES_SOURCE}/setup_utilities.sh -y` post-step | off | Skips the post-deploy `.utilities/` symlink wiring for claude and codex targets. |

## Underlying env passthrough

The orchestrator forwards env vars to the deployer subprocess. Precedence: explicit CLI flag > inherited env > pack-root `.env` > markdown_library default.

| target | env vars forwarded |
|---|---|
| claude | `INSTALL_GLOBAL_CLAUDE_MD`, `INSTALL_REMOTE_MCP`, `INSTALL_LAUNCHD`, `INSTALL_LM_STUDIO`, `INSTALL_LSP_BINARIES`, `LSP_IP`, `LSP_USER`, `LSP_PASS`, `LSP_REMOTE_HOME`, `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, `LM_STUDIO_URL`, `BRAVE_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `MY_GITEA_API_TOKEN`, `MY_GITEA_HOST`, `MY_GITEA_PORT` |
| codex | `CODEX_HOME`, `INSTALL_CODEX_HOOKS`, `INSTALL_EXEC_POLICY`, `INSTALL_LM_STUDIO`, `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, `LM_STUDIO_MODEL`, `LM_STUDIO_CONNECT_TIMEOUT`, `LM_STUDIO_MAX_TIME`, `CODEX_MAX_QUALITY_ATTEMPTS`, `CODEX_TURN_CONTENT_LIMIT` |
| gemini | `GEMINI_HOME`, `INSTALL_GEMINI_HOOKS`, `INSTALL_LM_STUDIO`, `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, `LM_STUDIO_MODEL`, `GEMINI_TURN_CONTENT_LIMIT` |
| openai | `OPENAI_TARGET_HOME`, `LM_STUDIO_HOST`, `LM_STUDIO_PORT`, `LM_STUDIO_MODEL`, `LM_STUDIO_CONTEXT`, `LM_STUDIO_AUTOLOAD_MODELS`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` |

Secret-keyed values appear in `state.json` `feature_flags` and in the `flag_fingerprint` as `key=<redacted>`. Raw secrets never enter logs or hash inputs.

## Example

```
gc magi install --target claude --dry-run --non-interactive
gc magi install --target claude
gc magi install --target codex --home "${HOME}/.codex"
gc magi install --target all --skip-utilities
```

## bd note

Emits `pack:magi:install` + `verb:install` + `target:<name>` + `outcome:<rc>` + `role:root`. Re-runs within `IDEMPOTENT_WINDOW_SECONDS=300` reuse the prior bead when the fingerprint matches and the prior bead closed with `outcome:0`. `--no-bd` disables this.
