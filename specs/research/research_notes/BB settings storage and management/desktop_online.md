# BB desktop saved servers and local settings

## Where are desktop settings stored, and what is verified on this Mac?

### Takeaway
The desktop's saved server connections are local Electron state, separate from a BB server's settings database and `~/.bb/config.json`. This Mac's installed application reports 0.43.3; its actual bundled code implements multiple saved custom servers, matching the public desktop-v0.43.3 release source.

### Cited Findings
- Desktop startup joins Electron `app.getPath("userData")` with `server-target.json`. On this Mac the observed file is `/Users/csells/Library/Application Support/bb/server-target.json`. Source establishes the location rule; read-only local inspection establishes the expanded path. [Release startup source](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L2374-L2425)
- The exact schema is `{connectServer?: {handle,name,url}|null, customServerUrl: string|null, customServerUrls: string[], target: "builtin"|"connect"|"custom"}`. It is strict: unknown fields invalidate the entire persisted payload; invalid or missing data falls back in memory to This Mac. `customServerUrls` defaults to [] for legacy files. [Release schema and parser](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/server-target.ts#L44-L95)
- `window-state.json` in the same userData directory stores a `windows` array with each window's stateKey, bounds, fullscreen and maximized flags. It is window placement, not the saved server list. [Window storage](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/window-state.ts)
- `connect-credential.bin` in that directory is the desktop's encrypted Connect credential. Electron safeStorage is supplied as its encryption implementation; it is not a plaintext config file. The official multi-device guide says the desktop keeps its own OS-keychain-encrypted credential and does not hold the server pairing secret. [Credential cache](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/connect-credential-cache.ts), [startup wiring](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L2422-L2425), [official device guide](https://github.com/get-bb/bb/blob/main/docs/multiple-devices.md#point-the-desktop-app-at-another-bb)
- Local read-only inspection on 2026-09-21 verified `/Applications/bb.app/Contents/Info.plist` and app.asar package.json both report **0.43.3**. Extracted bundled main.js contains Add Server and customServerUrls matching the public release source. Multiple-server support is a stock release feature, not evidence of a local patch. [Public release server storage](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/server-target.ts), [release menu](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/menu.ts#L80-L123)

### Inferences
- Direct editing is possible but is an internal schema-level operation rather than a documented desktop CLI configuration API. Quit the desktop, make a preserving backup, modify only understood fields, and relaunch. This follows from its startup-only `load()` and in-memory setters that rewrite the file; editing while running can be overwritten by the next save. `bb-app config refresh` concerns different files and cannot be assumed to reload this desktop file. [Startup load](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L2410-L2413), [store persistence](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/server-target.ts#L106-L119), [package refresh documentation](https://github.com/get-bb/bb/blob/main/docs/configuration.md#precedence)

### Gaps
- No server, GUI, configuration, credential, or data modifications were made in this research. No desktop CLI for listing/renaming this saved-server registry was established. Another researcher covers actual bb/bb-app command capabilities.

## How does the GUI manage this list, including the default name?

### Takeaway
The native Window → Server menu is the saved connection manager. Settings → Machines is scoped to execution machines belonging to the selected server. The three observed entries refer to two server URLs: the Connect-sourced `default` name and a custom hostname entry both address the Mac mini.

### Cited Findings
- The Window/Server submenu contains the server radio list, Add Server…, and Set Server URL…. It has no Rename command and no separate Forget Server menu item. [Release menu implementation](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/menu.ts)
- Add Server opens the URL dialog empty and saves another URL. Set Server URL opens the most recently selected custom URL, **even if the current active target is Connect or This Mac**. Saving replaces that custom URL; leaving it blank removes that saved custom entry. The dialog itself says `Edit this saved server. Leave empty to remove it.` [Dialog invocation](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L1568-L1595), [dialog implementation](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/server-url-dialog.ts)
- Custom entry labels are derived from the URL host (hostname and port), not a separate name field. Connect labels come from the account server record's `name`; the selected Connect record is cached as `connectServer` if unavailable from account discovery. [Menu construction](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L680-L744)
- New account discovery replaces cached name/url for the same Connect handle; locally editing `connectServer.name` is not an authoritative cloud rename and can be overwritten. [Account sync handler](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L2438-L2450), [refresh method](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/server-target.ts#L180-L190)
- The selected `connect` target authenticates through Connect and starts session renewal. A manually saved `custom` target directly loads its URL and does not invoke that Connect-specific renewal branch. Thus duplicate URLs are not entirely equivalent connection modes. [Target application](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L1467-L1509)
- Official docs distinguish one central server that owns settings/database from enrolled execution machines. Settings → Machines adds a host daemon to that selected server, not another independently stored server workspace. [Official multi-device guide](https://github.com/get-bb/bb/blob/main/docs/multiple-devices.md#add-an-execution-machine)
- Safe local whitelist inspection (2026-09-21) found the following data. Its keys and semantics are backed by the source; these values describe this particular Mac, not a universal BB default. [Storage schema](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/server-target.ts)

```json
{
  "connectServer": {
    "handle": "csells-mac-mini",
    "name": "default",
    "url": "https://csells-mac-mini.getbb.app"
  },
  "customServerUrl": "https://csells-mac-mini.getbb.app",
  "customServerUrls": [
    "https://csells-hillsboro.getbb.app",
    "https://csells-mac-mini.getbb.app"
  ]
}
```

This is a **partial inspection excerpt**, not a complete replacement config: the required `target` was intentionally omitted from this excerpt. Never paste this as a replacement file.

### Inferences
- The user's `default` is the Connect account's server name, not a built-in Mac-mini alias or third machine. Changing that authoritative name should occur in the Connect account management surface, if supported; merely editing the cached name cannot reliably accomplish it. [Menu construction](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L680-L744), [name refresh](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/main.ts#L2438-L2450)

### Gaps
- No cloud dashboard rename flow was validated in this assignment. Do not claim a specific cloud UI rename affordance without separate evidence.
- The current official docs describe `a custom URL` singular; the actual release source and installed bundle support an array. For this specific capability the implementation is more precise than the prose. [Guide](https://github.com/get-bb/bb/blob/main/docs/multiple-devices.md#point-the-desktop-app-at-another-bb), [release source](https://github.com/get-bb/bb/blob/desktop-v0.43.3/apps/desktop/src/server-target.ts#L53-L60)
