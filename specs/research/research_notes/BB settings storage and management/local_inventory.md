# Installed BB settings inventory and management

## Where are settings actually stored on this installation?

### Takeaway
The installed desktop application is BB 0.43.3. Its local saved server connections and its server-backed preferences use different stores: the server picker is a desktop JSON file, while most Settings-page preferences live in the selected server's SQLite database.

### Cited Findings
- Installed CLI `--version` and package metadata both report 0.43.3. Source inspected September 21, 2026: [installed package](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/package.json).
- The local desktop's actual file is `/Users/csells/Library/Application Support/bb/server-target.json`. Its safe fields currently contain `target: "custom"`, `customServerUrl: "https://csells-mac-mini.getbb.app"`, and `customServerUrls` with Hillsboro and Mac mini. `connectServer` is `{name:"default",handle:"csells-mac-mini",url:"https://csells-mac-mini.getbb.app"}`. This directly verifies three menu entries represent two endpoints. [Observed file](/Users/csells/Library/Application%20Support/bb/server-target.json).
- The same Electron user-data directory contains `connect-credential.bin`, `window-state.json`, `Preferences`, `Local Storage`, `Session Storage`, `Cookies`, and `Partitions`. These are client state, not the selected remote server's database. Only file names/schema were inspected for potentially sensitive storage. [Observed directory](/Users/csells/Library/Application%20Support/bb).
- The local default data directory is `/Users/csells/.bb`; `bb.db` exists with SQLite WAL/SHM files. There is currently **no** `config.json`, `env.json`, or `client.json` there. These are optional managed files, not prerequisites for a functioning app. Default data location may be changed using `BB_DATA_DIR` or launcher `--data-dir`; `~` is expanded and blank values are rejected. [Installed runtime source](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js:15077).
- Read-only schema inspection of local `bb.db` confirms tables `app_settings` (including keybinding overrides), `app_settings_values` (`key,value,updated_at`), `ui_preferences` (`key,value_json,revision,updated_at`), `app_theme`, `system_experiments`, `plugin_settings` (`plugin_id,key,value,updated_at`), `plugin_kv`, and `hosts`. No preference/credential/thread row values were dumped. [Observed SQLite schema](/Users/csells/.bb/bb.db).
- Hillsboro read-only SSH inspection confirms `/home/ubuntu/.bb/bb.db` and auth files exist, while `/home/ubuntu/.bb/{config,env,client}.json` do not. Its `/home/ubuntu/.config/systemd/user/bb.service` supplies environment keys `PATH`, `BB_CLAUDE_CODE_EXECUTABLE`, and `BB_TELEMETRY`. The service unit, rather than a nonexistent env JSON, supplies these overrides. [Previously documented Hillsboro environment](/Users/csells/Code/gastownhall/gascity-packs/specs/research/bb-hillsboro-verification-2026-09-19.md); direct read-only SSH observation September 21, 2026.

### Inferences
- Switching the desktop server does not copy or merge settings between Mac mini and Hillsboro. The local `~/.bb/bb.db` is not evidence of the remote selected server's current preferences.
- The `default` label currently comes from saved Connect metadata; it is not a third execution machine or a third database endpoint.

### Gaps
- One bounded `ssh mini hostname` retry failed authentication (`Permission denied (publickey,password,keyboard-interactive)`). Therefore the mini's actual current remote data-directory override was not freshly verified. Do not claim its `~/.bb` path was confirmed by SSH in this research.
- Desktop-server rename/edit semantics are covered by the other researcher. This inventory does not establish direct `server-target.json` editing as a supported public interface.

## Which CLI and GUI surfaces manage which settings?

### Takeaway
`bb settings` and plugin commands operate on the connected server. `bb-app config`, `bb-app env`, and `bb-app client` manage local files for the launcher/client. None of those file commands is a general-purpose editor for the desktop Window → Server list.

### Cited Findings
- The actual CLI is available through `/opt/homebrew/bin/node /Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb.js`; launcher commands use adjacent `bb-app.js`. Bare `bb` is not on this shell's PATH. Live `bb guide settings`, `bb settings --help`, `bb-app --help`, and `bb plugin config --help` were read. [Installed bb CLI](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb.js), [launcher](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js).
- Server-backed CLI includes `bb settings show`, `bb settings general <key> <value>`, `bb settings completed-turns`, `bb settings keyboard list|hints|set|reset`, `bb settings experiment <key> <value>`, and `bb settings ui list|get|set|reset`. The live guide explicitly calls General and Keyboard server-backed and immediately shared by connected windows. Sidebar UI preferences are revisioned server state, while sidebar width/open state and microphone device selection remain client-local. [Live guide implementation](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb.js); authoritative upstream configuration overview: [official configuration docs](https://github.com/get-bb/bb/blob/desktop-v0.43.3/docs/configuration.md).
- Plugin settings use `bb plugin config <id>` to show, `bb plugin config <id> set <key> <value>`, or `... unset <key>`. Keep Awake and Concurrency Limit also supply dedicated plugin CLI commands and autosaving GUI settings pages. [Live CLI](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb.js), [skill app-settings reference](/Users/csells/Code/csells/agent-skills/skills/bb-cli/references/app-settings.md).
- `bb-app config [list]`, `set <key> <value>`, `unset <key>`, and `refresh` manage `<data-dir>/config.json`. Its top-level schema supports `config`, `customAcpAgents`, `customModels`, `sharedSkillRoots`, `serverHeaders`, `machineCredential`, `connectMachineId`, and `serverUrl`. Managed `config` keys are `BB_APP_URL`, `BB_INFERENCE`, `BB_INFERENCE_FALLBACK`, `BB_LOG_LEVEL`, and `BB_TRANSCRIPTION`. `BB_SERVER_URL` is additionally accepted by the command and maps to top-level `serverUrl`. [Installed config schema](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js:14795), [CLI help implementation](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js:16394).
- `bb-app env [list]`, `set <key> <value>`, and `unset <key>` manage `<data-dir>/env.json`, shaped `{"env":{"NAME":"string value"}}`. The list output masks each value as `<set>`. The file itself is plaintext, so do not share it indiscriminately. [Installed env schema](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js:14891), [masking implementation](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js:16543).
- `bb-app client ssh-target list|set|remove` manages `<data-dir>/client.json`, shaped `{"servers":{"https://server-origin":{"hosts":{"host-id":{"sshAuthority":"ssh-target"}}}}}`. This maps server/host identities to remote-editor SSH targets. It does **not** populate Window → Server. [Installed client schema](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js:14968), [skill remote-editor guidance](/Users/csells/Code/csells/agent-skills/skills/bb-cli/SKILL.md).
- `bb machine list|show|rename` operates on server execution machines. `bb server` is described as move/export/import, not saved desktop connection management. [Live command help](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb.js).

### Inferences
- A command executed locally does not automatically follow the desktop server picker. Inspect/target the CLI connection deliberately; run on the intended server over SSH for its local managed files. Never assume changing MacBook `~/.bb/config.json` edits Hillsboro's runtime configuration.
- Use supported GUI/CLI for database preferences. Direct SQL bypasses application validation, revision checks, and notifications; it is not an ordinary user configuration-file interface.

### Gaps
- No live preference mutation was performed, because this request is research. Successful help/schema inspection establishes syntax and storage design, not that a specific proposed mutation has been tested.

## How do precedence, reloads, and direct-file edits work?

### Takeaway
Managed JSON changes can be reloaded, but startup-only settings require a restart. Direct-file editing is reasonable for documented managed JSON structures when backed up and validated, while SQLite and Electron internal state require more care and should normally be changed through supported interfaces.

### Cited Findings
- For ordinary managed environment merging, the launcher combines inherited process environment, then `config.json`'s `config` map, then `env.json`'s `env` map; later entries win. Target URL resolution is explicit `--server-url`, then `config.serverUrl`, then managed `BB_SERVER_URL`, then the default loopback URL. [Merge and URL precedence](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js:15991).
- `config`/`env` writes attempt POST `/api/v1/system/config/reload`. If no server is reachable, the file remains saved and the command states it applies next start. `bb-app config refresh` requires a reachable server and reports startup-only keys needing restart. `bb settings reload` is the server API-facing counterpart. [Reload implementation](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js:16643).
- `BB_LOG_LEVEL` is startup-only even under `config`. Under `env`, startup-only keys include `BB_APP_SURFACE`, `BB_APP_URL`, `BB_DATA_DIR`, `BB_DEV_APP_PORT`, `BB_EXTERNAL_URL`, `BB_HOST_DAEMON_PORT`, `BB_INFERENCE`, `BB_INFERENCE_FALLBACK`, `BB_INHERITED_SKILLS_ROOTS`, `BB_LOG_LEVEL`, `BB_MANAGED_DEV_BUILTIN_PLUGIN_HOT_RELOAD`, `BB_POSTHOG_API_KEY`, `BB_SERVER_BIND_HOST`, `BB_SERVER_PORT`, `BB_TELEMETRY`, `BB_TRANSCRIPTION`, and all `BB_FF_*`. Four model/app keys (`BB_APP_URL`, `BB_INFERENCE`, `BB_INFERENCE_FALLBACK`, `BB_TRANSCRIPTION`) can instead update live through `bb-app config`. [Exact startup-only help](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js:16415).
- The launcher prints `bb-app stop && bb-app start`, or desktop app restart, as application mechanisms for startup-only changes. For a systemd-managed Hillsboro deployment, respect its actual service ownership rather than starting a competing unmanaged server. [Launcher restart notice](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js:16671), [Hillsboro deployment record](/Users/csells/Code/gastownhall/gascity-packs/specs/research/bb-hillsboro-verification-2026-09-19.md).
- Managed JSON is parsed and validated; invalid JSON or schema errors fail rather than silently succeeding. Missing files default to empty configuration. Custom-model/ACP entries have per-entry validation, with invalid entries warned/ignored. [Read/validation code](/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb-app.js:16025).

### Inferences
- Before direct JSON edits, make a private dated copy, preserve unrelated fields, validate JSON/schema, apply the documented refresh or restart appropriate to the affected setting, and verify through the running app. Do not truncate/reset files or use an empty database as a test.
- For database backups while the server runs, use SQLite's backup mechanism or a BB-supported export rather than copying only `bb.db` and omitting live WAL contents. Raw DB replacement/editing is outside this research's recommended management path.
- `server-target.json` belongs to the desktop process, so directly editing it while that process retains its own state risks overwritten changes. Prefer the native menu and treat its internal format as version-specific.

### Gaps
- We have not tested whether manually editing Electron `server-target.json` reloads live; do not promise it. Another researcher is tracing the desktop implementation.
- Managed env values are plaintext; actual secret permissions vary by file/deployment and were not modified or fully audited by this read-only inventory.
