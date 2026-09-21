# BB server settings storage and management (official online research)

## Where does BB 0.43.3 store settings?

### Takeaway
BB has several independent settings stores: launcher JSON files, server SQLite settings, client-local UI storage, and native desktop connection settings. The native desktop connection store is covered by the other researcher; do not equate the launcher serverUrl with the desktop saved-server menu.

### Cited Findings
- Research scope is the public get-bb/bb repository, release tag desktop-v0.43.3, commit e865697f56bea89f3413dd4cc7fae964850d20a0. The official changelog dates 0.43.3 to September 18, 2026 and explicitly introduces saved addresses in the desktop Window → Server menu. [Official changelog](https://getbb.app/changelog), [release source](https://github.com/get-bb/bb/tree/e865697f56bea89f3413dd4cc7fae964850d20a0).
- Production defaults to the home directory's `.bb` folder; the SQLite filename is `bb.db`. The runtime resolver accepts `BB_DATA_DIR`, and launcher flags can choose another directory. This is source-verified, not a guess about Application Support. [Runtime path resolver](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/runtime.ts), [database path selection](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/database.ts).
- `<dataDir>/config.json` holds structured launcher configuration; `<dataDir>/env.json` holds an `env` object of string values. The config schema has top-level `config`, `serverUrl`, `customModels`, `customAcpAgents`, `sharedSkillRoots`, plus installer-managed credential fields. The `config` object supports BB_APP_URL, BB_INFERENCE, BB_INFERENCE_FALLBACK, BB_LOG_LEVEL, BB_TRANSCRIPTION. [Exact JSON schemas and paths](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/bb-app-managed-config.ts).
- `<dataDir>/client.json` is the local editor/SSH host-mapping file; it is not the native desktop server-menu list. [Client configuration schema](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/client-config.ts).
- Database schema separates `app_settings_values` (key/value settings), `ui_preferences` (key/value/revision), `plugin_settings` (plugin-id/key/value), and `environment_variables` (encrypted values with optional project scope). [SQLite schema](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/db/src/schema.ts). General preferences read/write `app_settings_values`; keyboard overrides are stored there too. [App settings persistence](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/db/src/data/app-settings.ts).
- GUI preferences are principally server-backed, so windows attached to the same server see the same settings. [Official CLI app-settings reference](https://github.com/get-bb/bb/blob/desktop-v0.43.3/plugins/bb-guide/skills/bb-cli/references/app-settings.md).

### Inferences
- Mac mini and Hillsboro therefore each own their workspace settings/database. Changing local launcher config does not edit a remote server's settings. This follows from server-backed API storage and machine-local launcher paths.
- There is no single settings.json that fully represents BB's settings. Preserve the whole relevant data directory for complete backups rather than assuming config.json includes the database and secrets.

### Gaps
- No user database was read. The local installed package.json was read solely for version/repository metadata: bb-app 0.43.3 and github.com/get-bb/bb. Actual live directories for each deployed machine require local/remote read-only verification by the coordinator.
- Native Electron connection files, cookies and client-local preferences are a separate assigned investigation.

## Which CLI and GUI controls manage each layer?

### Takeaway
Use `bb-app config/env` for launcher files, `bb settings` for the selected server's GUI preferences, and `bb plugin config` for plugin options. They are separate command families and do not provide interchangeable views.

### Cited Findings
- Launcher supports `bb-app config list`, `set <key> <value>`, `unset <key>`, `refresh`; bare `config` displays help. There is no `config get`. `BB_SERVER_URL` or alias `serverUrl` maps to top-level serverUrl; five runtime/logging keys map inside `config`. `bb-app env list/set/unset` operates on env.json; list redacts all values. [Launcher implementation and help](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/bb-app/src/launcher.ts#L1454-L1630).
- `bb-app client ssh-target list [--json]`, `set <server-origin> <ssh-target> [--host-id <id>]`, and `remove <server-origin> [--host-id <id>]` manage local editor SSH mappings. [Launcher client help](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/bb-app/src/launcher.ts#L1501-L1512).
- Read server settings with `bb settings show --json`; update general preferences with `bb settings general <key> <value>`. Other families are `settings completed-turns`, `settings ui list/get/set/reset`, `settings experiment`, and `settings keyboard list/set/reset/hints`. The code sends these through the server SDK rather than writing local JSON. `bb settings reload` calls the server managed-config reload API. [CLI settings implementation](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/cli/src/commands/settings.ts).
- Settings → General, Providers, and Keyboard correspond to server-backed settings. General setter accepts schema keys present in `generalSettings`; boolean values include true/false/on/off and null clears nullable settings. Sidebar preference writes use revisions to avoid conflicting updates. [Official app settings CLI reference](https://github.com/get-bb/bb/blob/desktop-v0.43.3/plugins/bb-guide/skills/bb-cli/references/app-settings.md).
- Settings → Environment variables edits encrypted global/project execution variables; Project settings → Advanced settings exposes the project scope. CLI uses `bb machine env list`, `set NAME`, `unset NAME`, with optional `--project <id>`. Set receives the value from stdin. Encryption needs `<dataDir>/machine-environment-key` as well as the database. This is distinct from launcher env.json. [Machine environment documentation](https://github.com/get-bb/bb/blob/desktop-v0.43.3/docs/configuration.md#machine-environment).
- Plugin-specific options use `bb plugin config <id> set <key> <value>` and plugin settings GUI pages. Official plugins track bundled app releases; direct git/npm installs have explicit update commands. [Configuration documentation](https://github.com/get-bb/bb/blob/desktop-v0.43.3/docs/configuration.md#plugin-updates).

### Inferences
- Recommended read-only discovery for the user is `bb settings show --json`, `bb settings ui list --json`, `bb settings keyboard list --json`, and `bb-app config list`/`bb-app env list`, with the target server/SSH session explicitly selected. Commands that edit launcher config should be run on the machine running that launcher.
- Prefer the matching CLI/API over direct SQL because it validates settings and broadcasts updates. No database editing was performed.

### Gaps
- This investigation does not claim the desktop connection entries are available through bb settings. That menu's exact schema/API is covered separately.
- Plugin config command availability varies by plugin/schema; the source schema confirms where settings live, not that every plugin setting is exposed identically.

## Can the files be edited directly, and when do changes apply?

### Takeaway
Managed JSON files can be edited, but they use strict structured schemas and require a reload; startup-only values require a full restart. They are not equivalents of the server database or desktop saved-server store.

### Cited Findings
- Documented precedence is explicit launcher flags, persisted managed values, shell environment, defaults. CLI writes ask the local running server to reload; if absent, changes apply next launch. Manual edits require `bb-app config refresh`. Non-default instances need matching data-dir and server-port. Runtime config keys reload, while BB_LOG_LEVEL and startup environment entries require a full launcher/desktop restart. [Pinned configuration documentation](https://github.com/get-bb/bb/blob/desktop-v0.43.3/docs/configuration.md#precedence).
- Config JSON has strict root keys; arbitrary GUI setting names do not belong there. Example schema-compatible fragment: `{"config":{"BB_APP_URL":"https://example.getbb.app"},"serverUrl":"https://example.getbb.app"}`. Env file shape: `{"env":{"EXAMPLE_NAME":"value"}}`. These examples illustrate structure only, not recommended replacements for existing files. [Config/env schema](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/bb-app-managed-config.ts).
- Managed-file writes take a lock, write an exclusive temporary file at mode 0600, then rename it into place. CLI writes preserve and merge existing managed content. [Atomic managed JSON writer](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/managed-json-file.ts), [launcher config merge/write](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/bb-app/src/launcher.ts#L1235-L1241).
- `BB_SERVER_URL` tells standalone CLI/host connections where to connect; it does not change the full bb-app launcher's local listening address. `BB_APP_URL` is the human-facing URL used for links/origins. [Configuration common keys](https://github.com/get-bb/bb/blob/desktop-v0.43.3/docs/configuration.md#common-keys).

### Inferences
- For an authorized direct edit, first preserve the original, retain every unrelated field, validate JSON/schema, then refresh or restart as appropriate. Do not replace whole files with the example fragments.
- Do not manually modify installer-managed credential/header fields or SQL tables to rename GUI workspaces. Those layers have distinct ownership and semantics.

### Gaps
- Source development additionally loads .env files, but this is not the packaged desktop workflow and was not deeply audited.
- Environment variables set in GUI are not retroactively injected into already-running terminals; official docs specify future operation/turn application. No live process was restarted or altered during this research.
