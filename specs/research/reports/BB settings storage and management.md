# BB separates connections from workspace settings

**BB does not have one settings file.** Your desktop's saved server connections live in `/Users/csells/Library/Application Support/bb/server-target.json`; most preferences shown inside BB Settings live in the **selected server's SQLite database**. Launcher configuration has separate optional JSON files under the relevant machine's BB data directory, normally `~/.bb`. Consequently, **Window → Server** and **Settings → Machines** manage different objects: the former selects a workspace connection, while the latter manages execution machines within that workspace. Your three menu entries resolve to two endpoints; `default` is the Mac mini's **Connect server record name**, not an intrinsic Mac mini alias. This report combines official online documentation, release source, and read-only inspection on **September 21, 2026**, scoped to installed **BB 0.43.3**. No settings, credentials, services, or data were changed during this research. ([Desktop source](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/server-target.ts), [official device guide](https://github.com/get-bb/bb/blob/desktop-v0.43.3/docs/multiple-devices.md))

## The desktop menu owns your saved connections

BB 0.43.3 stores desktop connection state beneath Electron's user-data directory. On this Mac, the verified file is **`/Users/csells/Library/Application Support/bb/server-target.json`**. Its fields include `target` (`builtin`, `connect`, or `custom`), the selected custom URL, an array of saved custom URLs, and a cached Connect server record. This is stock release functionality: the installed application and bundled package both report 0.43.3, and its bundled implementation matches the release's multiple-server support. ([Startup path](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L2374-L2425), [strict storage schema](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/server-target.ts#L44-L95))

Read-only inspection established the following current connections. The active target was `custom`, with the Mac mini URL selected; that selection is a point-in-time observation, not a default imposed by BB.

| Menu entry | Source of the label | Endpoint |
|---|---|---|
| `default` | Cached/discovered Connect server `name`; handle `csells-mac-mini` | `https://csells-mac-mini.getbb.app` |
| `csells-mac-mini.getbb.app` | Host portion of a saved custom URL | `https://csells-mac-mini.getbb.app` |
| `csells-hillsboro.getbb.app` | Host portion of a saved custom URL | `https://csells-hillsboro.getbb.app` |

**These entries are not listed in Settings.** The native **Window → Server** submenu contains the connection list, **Add Server…**, and **Set Server URL…**. Add Server opens an empty URL dialog and saves another connection. Set Server URL edits the most recently selected custom URL—even when the currently active target is Connect or This Mac. Its dialog says an empty value removes that saved custom entry. There is no separate Rename command, and custom entries have hostname-derived labels rather than editable names. ([Menu](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/menu.ts#L80-L123), [dialog selection](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L1568-L1595), [URL dialog](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/server-url-dialog.ts))

The previous description of `default` as an automatic Mac mini alias was imprecise. Its text comes from the Connect account's server record. Editing the cached `connectServer.name` would not reliably rename that record: account discovery refreshes the cached name and URL for the same handle. No authoritative cloud rename workflow was validated in this research, so no specific dashboard rename instruction is claimed. ([Label construction](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L680-L744), [account refresh](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L2438-L2450))

The two Mac mini entries also differ operationally. A **Connect target** authenticates through Connect and starts its session-renewal path. A **custom URL target** loads the URL directly and does not invoke that Connect-specific renewal branch. A clearer hostname label therefore does not make the custom entry entirely equivalent to selecting the Connect record. This does not establish a particular expiration time or prove every custom connection will fail; it establishes the different desktop authentication paths. ([Target application](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L1467-L1509))

## Settings belong to several distinct stores

The table separates storage ownership from the interface used to manage it. **A local file on your Mac does not configure Hillsboro simply because the desktop is viewing Hillsboro.** Conversely, server-backed preference commands apply to whichever server the CLI connects to. ([Configuration guide](https://github.com/get-bb/bb/blob/desktop-v0.43.3/docs/configuration.md), [app-settings reference](https://github.com/get-bb/bb/blob/desktop-v0.43.3/plugins/bb-guide/skills/bb-cli/references/app-settings.md))

| Store | Contents and scope | Supported management; application behavior |
|---|---|---|
| Desktop `server-target.json` | Saved workspace connections and selected target | Window → Server; no corresponding saved-server CLI established. For direct edits, quit/relaunch the desktop. |
| Desktop `window-state.json` | Window bounds, maximized/fullscreen state | Normal window operations; not server settings. |
| Desktop `connect-credential.bin` | Encrypted desktop Connect credential | Connect sign-in flow; not a plaintext configuration file. |
| `<dataDir>/bb.db` | General settings, keyboard overrides, UI preferences, plugins, machines, and application data | Settings GUI, `bb settings`, plugin/machine commands; avoid direct SQL edits. |
| `<dataDir>/config.json` | Structured launcher configuration, models/ACP/skills, connection fields | `bb-app config`; manual changes require refresh, with startup-only values requiring restart. |
| `<dataDir>/env.json` | Launcher environment map | `bb-app env`; plaintext file, with reload/restart rules. |
| `<dataDir>/client.json` | Server/host-to-SSH mappings for opening remote editors | `bb-app client ssh-target`; does not populate the desktop server menu. |
| Database environment records plus `<dataDir>/machine-environment-key` | Encrypted global/project execution environment | Settings → Environment variables and `bb machine env`; distinct from launcher `env.json`. |

These locations and divisions follow the release's [desktop window store](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/window-state.ts), [credential cache](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/connect-credential-cache.ts), [managed-file schema](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/bb-app-managed-config.ts), [client schema](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/client-config.ts), and [database schema](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/db/src/schema.ts).

The usual data directory is **`~/.bb`**, overridden through `BB_DATA_DIR` or the launcher's `--data-dir`. On this Mac, `/Users/csells/.bb/bb.db` exists; optional `config.json`, `env.json`, and `client.json` are currently absent. Read-only SSH inspection confirmed `/home/ubuntu/.bb/bb.db` on Hillsboro and the same three optional files absent. Hillsboro instead gets some startup overrides from `/home/ubuntu/.config/systemd/user/bb.service`. The Mac mini's effective data-directory override was **not freshly verified**: a bounded SSH attempt failed authentication. Its default path follows the product design, but this report does not present it as a successful remote observation. ([Runtime resolver](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/runtime.ts), [database selection](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/database.ts), [local inspection notes](../research_notes/BB%20settings%20storage%20and%20management/local_inventory.md))

Most General and Keyboard settings are server-backed and shared among windows connected to that server. Some presentation state remains client-local, including sidebar width/open state and microphone selection. Electron's user-data directory also contains browser-style preferences, cookies, local/session storage, and partitions. Those are not a second copy of all server settings. ([Settings reference](https://github.com/get-bb/bb/blob/desktop-v0.43.3/plugins/bb-guide/skills/bb-cli/references/app-settings.md))

## The CLI has separate commands for each owner

For the connected server, read preferences using `bb settings show --json`, `bb settings ui list --json`, or `bb settings keyboard list --json`. General preference changes use `bb settings general <key> <value>`; UI preferences, experiments, keyboard overrides, and completed-turn behavior have their own subcommands. Plugin configuration uses `bb plugin config <id>` to inspect, followed by `set <key> <value>` or `unset <key>` where supported. **`bb machine rename` renames an execution machine; it does not rename a desktop connection or Connect server record.** ([Settings CLI](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/cli/src/commands/settings.ts), [live CLI inventory](../research_notes/BB%20settings%20storage%20and%20management/local_inventory.md))

For local launcher files, use `bb-app config list`, `set <key> <value>`, `unset <key>`, and `refresh`. There is no `config get` command in the verified release. `bb-app env list|set|unset` manages the separate launcher environment file; list masks values even though the file itself is plaintext. `bb-app client ssh-target list|set|remove` manages editor SSH mappings. For encrypted execution variables, `bb machine env list|set|unset`, optionally scoped by `--project`, is the appropriate family; its setter receives the value from stdin. ([Launcher help and implementation](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/bb-app/src/launcher.ts#L1454-L1630), [execution environment guide](https://github.com/get-bb/bb/blob/desktop-v0.43.3/docs/configuration.md#machine-environment))

Bare `bb` was not on this Mac shell's PATH during inspection. The installed CLI can nevertheless be invoked without installing another version:

```sh
/opt/homebrew/bin/node "/Applications/bb.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/dist/bb.js" settings --help
```

The adjacent `bb-app.js` supplies launcher commands. This invocation was established from installed files and live help; it is specific to this installation. Before running any mutation, select or verify the CLI's server deliberately. **The desktop picker is not a guarantee that an independently launched CLI points at the same endpoint.** ([Installed-command evidence](../research_notes/BB%20settings%20storage%20and%20management/local_inventory.md))

Three connection/configuration scopes explain the recurring URL confusion. `BB_SERVER_URL` directs standalone CLI/host connections; `bb-app config set BB_SERVER_URL …` persists that choice as top-level `serverUrl` in the launcher's managed JSON; the desktop's saved server list remains a separate `server-target.json` structure. The launcher resolves its connection URL from explicit `--server-url`, then persisted `serverUrl`, then managed environment `BB_SERVER_URL`, then its loopback default. None of those is the full launcher's local listening-address setting. **`BB_APP_URL` is another setting again:** the human-facing address used for links/origins. ([Configuration keys](https://github.com/get-bb/bb/blob/desktop-v0.43.3/docs/configuration.md#common-keys), [launcher source](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/bb-app/src/launcher.ts))

## Direct edits require the right schema and reload

Managed JSON is editable, but arbitrary Settings-page names do not belong in it. These minimal schema examples illustrate **structure only**, not replacement files or instructions to change your endpoints:

```json
{"config":{"BB_APP_URL":"https://example.getbb.app"},"serverUrl":"https://example.getbb.app"}
```

```json
{"env":{"EXAMPLE_NAME":"value"}}
```

The first represents `config.json`; the second represents `env.json`. Existing files can also contain model definitions, ACP agents, skill roots, and installer-managed connection/credential fields. Preserve those unrelated fields. The supported writers merge existing content, use locking, and write temporary files with restrictive permissions before atomic replacement, making CLI edits preferable for supported keys. ([Managed schema](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/bb-app-managed-config.ts), [atomic writer](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/config/src/managed-json-file.ts))

For a justified manual edit, preserve a private dated backup first, retain unrelated fields, validate the schema, and apply the corresponding refresh. Config/env commands attempt a managed-config reload automatically; manual changes require `bb-app config refresh`. `bb settings reload` reaches the server-facing reload API. `BB_LOG_LEVEL` and other startup-only environment values need a restart; four structured runtime keys—`BB_APP_URL`, `BB_INFERENCE`, `BB_INFERENCE_FALLBACK`, and `BB_TRANSCRIPTION`—can update through managed config. Match the correct data directory and server port. On Hillsboro, a required restart belongs to its existing systemd service, not a competing manually launched instance. ([Reload and precedence](https://github.com/get-bb/bb/blob/desktop-v0.43.3/docs/configuration.md#precedence), [launcher implementation](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/bb-app/src/launcher.ts))

Desktop `server-target.json` is an internal strict schema, not the managed launcher schema. Unknown fields invalidate its payload, so adding an invented label field is unsafe. Its startup load and in-memory persistence imply that direct editing should happen only **after quitting the desktop**, followed by relaunch; `bb-app config refresh` is not its reload mechanism. For database settings, prefer supported GUI/CLI operations to preserve validation, revision handling, and notifications. A complete backup must account for database state and needed encryption keys; copying only an active SQLite main file can omit pending WAL data. ([Desktop parser/store](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/server-target.ts#L44-L119), [startup load](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L2410-L2413), [database settings implementation](https://github.com/get-bb/bb/blob/desktop-v0.43.3/packages/db/src/data/app-settings.ts))

For your existing setup, the missing Settings entry is a **UI organization issue**, not evidence that Hillsboro or the Mac mini was never saved. The next improvement would be an authoritative Connect record rename or a richer desktop connection-management interface. Locally altering a cached name would obscure ownership and still leave discovery able to replace it; establishing the actual Connect rename capability is the remaining factual gap before promising a durable fix for `default`.
