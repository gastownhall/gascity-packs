# runtime-herdr-core

A Gas City **runtime pack**: runtime `herdr-core` runs agent sessions in
[herdr-core](https://github.com/herdrdev/herdr-core) (`hc`), the terminal
daemon the Herdr desktop app is built on. The pack ships one executable that
speaks the Runtime Provider Protocol (RPP v0). It is typed Python, standard
library only, Python 3.9 or later, so it needs no binary of its own.

## Status: runtime ops in, not released

The executable implements gc's runtime ops on herdr-core and is v2-ready:
it declares `observe.v1`, `report-attachment`, `report-activity`,
`city-scoped`, `conformance-faults`, `server-lifecycle`, `carrier.ops`,
`idle-boundary`, `input-outcome` and `fs.host` (locality `local`; see
[Host work](#how-sessions-run)), and passes
`gc runtime check` and `gc runtime conformance` against fake-hc (see
[Tests](#tests)). The pack is not in `registry.toml` yet: it is published
once it has run real cities on a pinned herdr-core. To use it, install the
pinned herdr-core with `gc herdr-core install` (see
[Install and commands](#install-and-commands)); `gc doctor` runs the
pack's [checks](#doctor). A `herdr-core` or `hc` on `PATH` is never used.

The pack needs a gc built from a gascity commit that contains `a07d754c75`
(gastownhall/gascity#9129), which no gc release does yet:
`gc version --long` names the commit a gc was built from, and in a gascity
clone `git merge-base --is-ancestor a07d754c75 <commit>` exits 0 when that
commit contains it. Never run the pack on a gc built from `5e24c6e2b9`
(gastownhall/gascity#9032) up to `a07d754c75`. Such a gc honors `fs.host`
without that commit's tmux fence, so when a session starts again it ends
every pane of a tmux server founded inside the session's box
(`tmux new -d`, or the user's default server when none was running, with
the user's own shells and editors), and drain-ack escalation can take such
a pane for a wedged session's agent and end it. The pack cannot refuse such
a gc: its handshake is fixed, gc passes its ops no version, and nothing
enforces a gc floor.

The runtime is named `herdr-core`, never `herdr`: `herdr` is a gc builtin,
and declaring it is a composition error (RUNTIME-SEL-007).

## Layout

```text
runtime-herdr-core/
  pack.toml                        [runtimes.herdr-core] -> assets/bin/gc-runtime-herdr-core
  mypy.ini                         mypy --strict; disallow_any_expr in rpp/ and herdrcore/
  commands/{install,status,upgrade,restart-core}/   gc herdr-core <verb>
  doctor/{hc-python,hc-binary,hc-core,hc-scope-hygiene,hc-state-perms}/   gc doctor checks
  assets/
    hc-pin.json                    the pinned herdr-core: version, minimum, tested, sha256 per platform
    bin/gc-runtime-herdr-core      0755, #!/usr/bin/env -S python3 -I -S
    bin/gc-herdr-core-launch       0755, the agent launcher hc runs in each terminal
    shim/hc.in                     the in-agent hc shim's template
    gc_runtime_herdr_core/
      main.py                      argv dispatch; reads os.environ (as do the launcher and shim)
      handshake.py                 the capabilities this build declares
      rpp/                         provider-neutral RPP kit
        exitcodes.py wire.py ops.py perop.py cancel.py redact.py flock.py
        statedir.py jsonval.py outcome.py
      hc/                          herdr-core client
        paths.py version.py client.py types.py parse.py errors.py
      herdrcore/                   runtime semantics
        ops_table.py context.py config.py core.py command.py naming.py
        records.py metastore.py procs.py attach.py activity.py reads.py
        lifecycle.py staging.py spawnfile.py envplan.py launch.py shim.py
        inputs.py screen.py readiness.py server.py corescan.py
        pin.py install.py admin.py commands.py doctor.py appvis.py infra_argv.py
  tests/
    fakehc/                        hc double (in process, or as a herdr-core binary) + vendored schema
    unit/                          the unit tier
    conformance.sh                 gc runtime check + gc runtime conformance against fake-hc
    infra_argv_drift.py            CI: the infrastructure argv table equals gc's at the pinned commit
```

## Install and commands

Import the pack under the binding `herdr-core` so its commands read as
below (`gc <binding> <verb>`); the pack's messages name them so.

```toml
[imports.herdr-core]
source = "<this pack>"
```

- **The pin.** `assets/hc-pin.json` names the one herdr-core version the
  pack installs (0.1.19), the oldest it drives, the versions it was tested
  against, and the release asset and sha256 of each platform's build
  (`linux-x86_64`, `linux-aarch64`, `macos-aarch64`, `macos-x86_64`, from
  herdr-core's release manifest). A missing or malformed pin fails every op
  that needs hc. Moving the pin is a pack release.
- **`gc herdr-core install`** checks that the release manifest agrees with
  the pin, downloads the asset and checks its sha256 against the pin before
  writing anything, reads the one `herdr-core` file out of the archive
  (nothing else is extracted, nothing is run), and renames a staged
  directory into place at
  `<password-database home>/.local/share/gc-runtime-herdr-core/hc/<version>/`
  (never `$HOME` or `XDG_DATA_HOME`). The binary and its directory are
  read-only, so `hc update` refuses to replace it, and `install.json`
  records what was installed. Older versions are collected; the pinned
  one, the most recently installed other one (to roll back to) and any a
  process still runs are kept, and nothing is removed when the process
  table cannot be read. When the pinned build is already installed and
  verifies against its `install.json`, nothing is fetched.
- **`gc herdr-core status`** reports the pin, the install and the city's
  core (version, pid, live terminals, whether the pack started it).
  `status --env` prints the core's discovery tuple:
  `env $(gc herdr-core status --env) herdr-app` connects the Herdr app to
  the city's core.
- **`gc herdr-core upgrade`** installs the pin, then hands the city's core
  over with `herdr-core server restart` under the pack's allowlist
  environment: hc keeps every program and its screen across a planned
  restart, so sessions keep running. A core started outside the pack is
  refused (the restart would keep its environment), and so is a city that
  drives its own `hc_bin` (the pack does not upgrade that build).
- **`gc herdr-core restart-core`** stops the city's own core and starts a
  fresh one under the allowlist: the fix for a core started outside the
  pack. Stopping a core ends its programs, so it refuses while the city
  runs or any terminal runs there (`gc stop` first). It refuses a core that is not the city's
  (another user's, or one with another hc session or state root). Its
  start clears `server-stop`'s stopped mark, as a session start does.
- **The binary.** The pinned install, unless the city's pack config
  (`<R>/pack/<city id>/config.json`) sets `hc_bin` and
  `"allow_unpinned": true`, an explicit choice to drive another build.

## Doctor

Each check is `doctor/<check>/run.sh` and runs as gc runs pack checks (the
pack directory as cwd, `GC_CITY_PATH` naming the city), resolving the
city's core as the ops do, within a 10 s budget (a check that runs out
warns). They only read: a check never starts a core or writes state.

| Check | Error | Warning |
|---|---|---|
| `hc-python` | no `python3`, or one older than 3.9 | |
| `hc-binary` | not installed; changed since install; from another release; `hc_bin` without `allow_unpinned` | installed without `gc herdr-core install`; writable; `hc_bin` with `allow_unpinned` |
| `hc-core` | down while the city runs (once a read found it down, and not stopped by `server-stop`: a city `gc stop` parked stays down, OK, until a session start); a failed start in the last 5 minutes; a core of the session on another socket; older than the minimum; started outside the pack; running a binary from outside the pack's install root (or other than `hc_bin` when the city sets one) | version differs from the pin (`upgrade`), including a core still running a build installed before the pin moved; an untested version; a package manager's hc; on Linux, no systemd user manager or lingering off (lingering on is disclosed as a note); inside gc's service cgroup; still running while the city is stopped |
| `hc-scope-hygiene` | the city's supervisor or controller, Dolt server or watchdog, or bd proxy carries `HC_SCOPE`, runs under a herdr-core holder or core, or in an `hc-hold-*`/`hc-serve-*` cgroup | its environment cannot be read |
| `hc-state-perms` | hc's state directories are not this user's 0700 directories, or `terminals.json` is readable by others through them (hc writes it with the umask's mode, which 0700 directories keep private) | |

`hc-scope-hygiene` attributes a process to the city by the city path in
its argv or config (`--config`, `--root`, the watchdog's arguments), by
`GC_CITY`, `GC_CITY_PATH` or `GC_CITY_ROOT` in its environment, or (a
supervisor or controller) by holding the city's controller socket. gc's
nudge pollers are left out: they are session-scoped and spawned from
agents by design.

## Herdr app labels (opt-in)

With `"app_visibility": "labels"` in the city's pack config, every
session's terminal is labelled `herdr.space=gc-<city>[-<rig>]` and
`herdr.tab=<its hc terminal name>`, which puts it on the Herdr app's
screens. It is off by default: the app sets `keep=true` on what it adopts,
so an agent that exits leaves a shell, which the pack reads as the
session's death (gc restarts it).

It is experimental: whether the Herdr app adopts ids in this style (it
names its own spaces and tabs with ids such as `s1` and `t2`) has not been
checked against the app yet, so the sessions may not appear there.

## How sessions run

- **One core per city and state root**, started by the pack with `herdr-core
  server start` under a minimal explicit environment: the password-database
  user, a fixed `PATH` (the hc binary's directory, then the system's), the
  locale, the discovery tuple, the pack-owned hc config, and the user
  manager's runtime directory and bus when they exist. No gc token or
  provider credential reaches the core. `start` refuses a core whose
  environment differs (someone else started it) and names the fix; a core
  listening on another socket for this session is refused too. A core hc
  placed under the systemd user manager is judged by its unit's environment
  file (hc writes the starter's environment to
  `$RUNTIME_DIRECTORY/environment`), not by the manager's own environment
  block. On macOS, where a process's environment is read cut at
  whitespace, a state root with whitespace is refused. A read that
  finds the core down answers unknown and starts it in the background, at
  most one at a time and none for five minutes after a failed start, and
  none while `server-stop` has parked the city (below).
- **The pack-owned hc config** (`R/hc-config/herdr-core/config.toml`): no
  typed notes into agents, 16 MB history, nothing from `~/.config/herdr-core`.
- **Names and identity.** A session is the newest terminal labelled with its
  exact gc name (`gc.session`), in its city (`gc.city`); each start gets a new
  incarnation nonce (`gc.obj`). The hc terminal name is a digest of the city
  and gc name, which makes a second `terminal.run` of a live session fail.
  Identity (`GC_SESSION_ID`, `GC_RUNTIME_EPOCH`, `GC_INSTANCE_TOKEN`,
  `GT_PROCESS_NAMES`) is written to `R/pack/<city id>/meta/<gc.obj>.json`
  (0600) before the terminal exists; the metadata ops read and write it.
- **Dead boxes.** A finished record, and a live one no longer running the
  program the pack started (a kept terminal's replacement shell, a lost
  holder), is a dead box: `peek` still reads its screen, `kill-object corpse`
  removes it, and a plain `start` recycles it.
- **The launcher.** hc gets only `TERM`; the session's environment, command
  and work directory travel in a spawn file on tmpfs (0600, created
  exclusively, never following links), which the launcher unlinks before it
  reads it. The launcher removes `HC_SCOPE` (hc's holder-loss sweep kills
  every process carrying it), `HC_SOCKET`, `HC_SESSION` and the core's own
  state and config directories the session does not set (the user's runtime
  directory and session bus stay, as in a tmux pane), applies the session
  environment (`""` unsets), puts the hc shim first on `PATH`, and execs the
  agent. When `start`'s probe (the launcher's exact `systemd-run --user
  --scope --slice=…` invocation, kept per core process on success and for
  five minutes on failure) shows a user manager can place it, the agent runs
  in its own scope under `GC_AGENT_SLICE` (the session's, else gc's, else
  `gascity-agents.slice`); otherwise, or when the launcher cannot run
  `systemd-run`, it starts unwrapped and `start` warns. The shim (one per
  city, in the city's pack state) gives in-agent `hc` the city core's exact
  tuple and refuses while the core is down instead of starting a second
  one.
- **Host work (`fs.host`).** It needs a gc that contains
  gastownhall/gascity#9129 (`a07d754c75`): a gc built from
  gastownhall/gascity#9032 (`5e24c6e2b9`) up to it honors `fs.host`
  without the tmux fence below, and ends the panes of a tmux server
  founded inside a box when the session starts again (see
  [Status](#status-runtime-ops-in-not-released)). Boxes run on gc's host
  as gc's user with gc's view of the filesystem, and the pack declares
  `fs.host` (with locality `local`, which gc requires for it). Into a name
  that holds no live box, gc then
  stages the work directory (`pack_overlay_dirs` with its
  `per-provider/<provider>/` slots, `overlay_dir`, `copy_files`, merging
  its hook and settings files), runs `pre_start` (fatal) before `start`
  and `session_setup` and the setup script (warnings) after it, on the
  host, and leaves those fields out of the start config. gc gives each of
  those commands the city's `[session] setup_timeout` (10 s unless set;
  once `setup_max_timeout` is set, it bounds only how long a command stays
  silent), where `start` gives each up to 30 s, so raise it for a
  `pre_start` that needs longer. `start` does
  exactly what its config carries (an omitted field is not staged or
  run), so a gc older than `fs.host` itself (gastownhall/gascity#9023),
  or one whose cached handshake predates the declaration, still sends
  them and `start` does that work as below; so
  does a current gc when it cannot read whether a live box holds the name
  (`observe` fails or answers unknown), so the pack's own staging stays
  load-bearing. gc also materializes skills and MCP for agents on this
  runtime (at the scope root, or in a worktree through a `pre_start`
  entry it runs on the host), where without `fs.host` it refuses an
  agent with effective MCP.
  `session_setup` gc runs comes after `start` returns, so after the first
  turn (`nudge`); gc runs it without `GC_TMUX_SOCKET`, so keep commands
  that drive tmux out of `session_setup` for this runtime. gc also reads
  the agent's transcripts on its own host for turn tracking (the agent
  gets gc's `HOME`, see below), and runs its process-table cleanup for the
  pack's sessions: before a session starts it ends its stopped
  incarnation's leftovers, the orphan sweep ends the leftovers of a
  closed session or of one stopped with no live box under its name, and
  drain-ack escalation looks for a wedged session's processes. A leftover
  is a process carrying the session's `GC_SESSION_ID` and `GC_CITY_PATH`
  that no box `inventory` lists carries. hc's core is started under an
  allowlist environment with no session's identity, so it is never one.
  Since gastownhall/gascity#9129, that cleanup never treats a tmux server
  or client carrying a `GC_SESSION_ID`, or anything in its panes, as a
  session's process for this pack (gc drops that fence only for a pack
  that declares `proc.exec` without `carrier.ops`, whose agent it reads as
  running in its box's tmux; this one declares `carrier.ops` and never
  `proc.exec`): a tmux server founded inside
  a box (`tmux new -d`, or the user's default server when none was
  running, which copies the box's environment) keeps every pane. What
  gc's docs leave over: a process that leaves such a pane and is adopted
  by init (or the user's subreaper) is no longer under tmux and counts as
  a leftover, so once a box has founded the user's default tmux server,
  something started there later can be ended as the session's leftover
  once it leaves its pane; a tmux session an agent starts inside a box is
  never cleaned up by gc; tmux is recognized by its process name (`tmux`,
  or the title a renamed tmux binary of up to 14 characters takes on
  Linux; on macOS only `tmux`), so a tmux under another name is not
  fenced; in a city that also runs ACP agents the fence covers their
  processes too; and drain-ack escalation finds nothing to end for this
  pack's sessions, so a wedged session's slot stays occupied until its
  box exits. `observe` reports
  `agent_pid`, a host pid: the agent's when it is asked about process
  names and finds one, else the box's program. The agent gets gc's `HOME`
  (unless the session environment sets it), so the transcripts gc reads
  under its own home are the ones the agent writes; the core keeps the
  password-database home.
- **Start** stages `pack_overlay_dirs`, `overlay_dir` (with
  `per-provider/<GC_PROVIDER>/`) and `copy_files`, runs `pre_start`
  (fatal), creates the terminal in `work_dir` (which must exist by then;
  the home without one), runs `session_setup` and the setup script
  (warnings), each only when the config carries it, then types `nudge` once the agent is ready (its prompt, read
  as gc reads a pane: the bottom-most prompt line, NBSP as a space, a box
  border skipped, and a numbered menu's cursor row no prompt; else its
  delay, at most 60 s as in gc; else its first status report; else settled
  output). A wait that runs out without readiness (a boot slower than the
  wait, a prompt prefix that never matches) types the turn all the same,
  as gc's tmux and herdr providers type it on a probe that timed out. A
  wait cut short by the op's deadline types it too once some screen
  settled during it, which is this pack's own choice, not gc's: gc's tmux
  provider returns before it types, and gc's herdr provider skips the turn
  and records it unconfirmed. When no screen settled, the turn is withheld
  instead, as a dialog may not be drawn yet. The pack stops waiting 5 s
  before its deadline, so with 5 s or less left it does not wait at all:
  only a ready prompt or a status report already there gets the turn.
  Whenever the turn is typed without readiness, `start` warns (`the first
  turn was typed without readiness: ...`). gc
  answers startup dialogs only once `start` returns, so a screen showing
  one of gc's known dialogs is never ready, and a dialog still on screen
  when the wait settles or ends withholds the turn with a warning and
  `GC_STARTUP_DELIVERY_UNCONFIRMED` in the metadata. A bare "rate limit"
  mention withholds the turn only on a menu: gc's provider rate-limit
  screen (the mention, in any case, with `Keep trying` and `Stop`) or a
  numbered menu's cursor row beside it. Once `start` returns, gc's startup
  pass answers a screen with a bare marker "Stop" (Down, Enter), so the
  turn's Enter would pick the menu's selected option first. With no menu
  (a status line's, a tip's) the mention is no dialog: with no prompt line
  on another line it keeps the wait going, and the wait's end types the
  turn. Known limit: a turn withheld over a
  dialog is not typed later, as gc answers the dialog but does not type
  an exec runtime's first turn after `start`; the marker is for
  operators. Any other menu gc does not know as a dialog gets the turn at
  the wait's end, as in gc. `session_live` (tmux
  theming and keybindings) is never run: herdr-core runs no tmux server,
  and run on the host it would reach a person's own; `start` warns that it
  is not applied. `terminal.run` is sent once: after a lost reply
  the start takes the terminal its `gc.obj` names, so a command never runs
  twice, and a start that fails while it creates the terminal ends its
  processes as `stop` does, by their `GC_INSTANCE_TOKEN` too, and keeps
  the metadata while its terminal may still run. When hc cannot read the
  created terminal afresh or list the city's boxes, it ends the terminal's
  tree (unless its pid started after the terminal was created, a recycled
  one) but scans nothing by the token, and leaves the box to gc's stop. A
  created terminal hc no longer holds is still scanned for by the token
  before its metadata, the token's only copy, goes. One that fails or is
  canceled later leaves the box, which gc stops. An agent that exits
  during startup fails the start, unless its lifecycle is `one_shot`.
  Staging does not merge: the files gc JSON-merges (`.claude/settings.json`,
  `.gemini/settings.json`, `.codex/hooks.json`, `.cursor/hooks.json`,
  `.agents/hooks.json`, `.github/hooks/gascity.json`) and a Kiro
  `AGENTS.md` already in the work directory are kept, with a warning. Only
  `per-provider/<GC_PROVIDER>/` is staged: a custom provider's family slot
  and `install_agent_hooks`' extra slots are not (gc stages those when it
  does the host work under `fs.host`). Staging and `copy-to` write nothing outside
  the work directory: nothing is written through a symlink below it (one
  where a file or directory would go fails the staging or the copy; gc
  writes through it), and a `copy_files` destination that leaves the work
  directory is skipped with a warning (gc adds its hook files with
  city-relative destinations meant for container providers). A
  `copy_files` entry or `copy-to` source that is its own destination is
  skipped, as in gc, and a file staged onto itself (a hard link, or an
  overlay that is the work directory) is left as it is, where gc's copy
  empties it.
- **Input.** gc drives a box only through the pack's own `nudge`, `peek`,
  `send-keys`, `interrupt` and `clear-scrollback` (`carrier.ops`); it never
  sends tmux commands, and `exec` exits 2 without reading them. `peek`
  shows the agent's screen and `set-meta`/`get-meta` keep its ready prompt
  (`GC_READY_PROMPT_PREFIX`, byte for byte), so gc can find a safe idle
  boundary (`idle-boundary`). Input goes to the current incarnation by
  address, and the four driving ops answer with a typed outcome
  (`input-outcome`): exit 0 when the input was delivered (a `nudge` may add
  one `delivered_unobserved` line), exit 80 with exactly one
  `{"outcome":…,"detail":…}` line for every other outcome, exit 1 when the
  outcome is unknown. A non-success word is never printed on exit 0, so
  every gc reads the same answer: one that does not read `input-outcome`
  sees exit 80 as an ordinary failure. See [Input outcomes](#input-outcomes).
- **Activity.** A program that never reported OSC 7501 status is active
  when its screen changes: `inventory` and `get-last-activity` read the
  screen of each such running agent (hc keeps no output time). `inventory`
  reads within its deadline, and a box whose screen it did not read on that
  pass reads as active now, never at an old time.
- **Stop and kill-object** end the whole process tree: descendants captured
  before hc's kill, the incarnation's re-parented processes (a daemon a
  live agent started, every child of one already gone) found by its
  `GC_INSTANCE_TOKEN` whatever the box's state, every process still the one
  captured (same start time) sent TERM then KILL. Every process carrying
  the token dies, one the agent meant to outlive it too. That is wider
  than gc's own orphan sweep, which for this pack ends only leftovers
  adopted by init or the user's subreaper, of sessions that are closed or
  stopped with no live box under their name: a shared per-user
  daemon first started from inside a box carries its token and dies with
  it, such as a Bazel or Gradle server, an ssh `ControlMaster` or a
  `gpg-agent`; the next use starts it again. One started during the kill
  (a TERM handler's `setsid` child) is found by scanning for the token
  again once the captured processes are dead, until a scan finds none (at
  most three more rounds). Infrastructure and its whole subtree is never
  killed: city infrastructure (gc's managed Dolt watchdog, bd's database
  proxy, gc's nudge poller) and, as gc never signals tmux, any tmux server
  or client (its executable, or a `tmux: server` / `tmux: client` title).
  A tmux server copies its founder's environment, so one founded from
  inside a box carries the token into every pane it later runs: the
  user's own shells and editors, or a whole tmux-runtime city when a gc
  command run in the box founded it. A herdr-core box never runs inside
  tmux; a tmux server the box itself runs under (hc's core started from a
  pane) fences none of the box's own tree. The pack's fence differs from
  gc's in two ways. gc's covers a tmux server or client carrying a
  `GC_SESSION_ID` and everything under it, and on Linux also recognizes a
  renamed tmux (a name of up to 14 characters) by its title; the pack's
  covers any tmux server or client, with or without a session id, but
  knows tmux only by the exact names above. So on Linux such a renamed
  tmux founded from a box is spared by gc's cleanup yet still dies with
  the box's stop, `kill-object` or `server-stop`. The
  fence covers only what is still under a server: a
  process that detaches from a pane of a server founded from a box (an
  `ssh -fN`, a `nohup` job whose shell exited, an agent such as `ssh-agent`
  started there) is re-parented out of it, still carries the token and
  dies; a renamed tmux (`tmux-next`) or a GNU `screen` server founded from
  a box is not fenced and dies with every window it runs; and work an
  agent runs under tmux (`tmux new -d 'make'`, a `tmux -D` server outside
  its process group) is fenced, so it outlives the box's stop. Other live
  sessions' trees are
  protected. Nothing under a process that
  cannot be read is signalled (an unreadable process may be
  infrastructure), nor is one that turns unreadable before its signal (its
  pid may have been recycled). When such a process is found, a process
  outlives its KILL, one still carries the token after the last round (a
  daemon that respawns), or the process table cannot be read (hc's
  kill still happens), the op exits 1 and the box and its metadata stay:
  gc's retry (the next stop or start, or a corpse kill) finds what is left
  by the token, and a `start` launches nothing while it may survive, for
  up to 15 minutes from its first refusal: a survivor that never goes (an
  unkillable process, one respawned from outside the kill, such as a user
  service that imported the box's environment, a process table that never
  reads) would refuse every start, so after that the start warns, naming
  what may survive, removes the old box and goes ahead beside it. The
  refusal names the time it stops. The first refusal is recorded in the
  box's metadata, else in a label of its terminal record; a box where
  neither takes it counts the 15 minutes from its creation, so one older
  than that is not refused at all, and a refusal names its creation. A
  process that does not carry the token, or whose environment cannot be
  read, is not found that way.
- **Attachment.** hc counts no viewers; a box is attached while the pack's
  `attach` runs (it holds a lock) or a `herdr-core|hc attach` process of this
  user targets it on this city's core. `is-attached` exits 1 when it cannot
  tell, including when such a process's environment cannot be read.
  `attach` checks the core answers first and runs `hc attach` with the
  core's allowlist environment, so it never starts a core on gc's.
- **Server teardown** (`server-lifecycle`). gc runs `server-stop` after
  it stops the city's sessions, at `gc stop` and at the orchestrator's
  shutdown, as a backstop: a session its own stops could not see ends with
  the core. With the core answering, every record of the city is ended as
  `stop` ends it (tree, token scan, infrastructure fenced); a terminal the
  city did not start (a person's, or one an agent opened through the
  in-agent `hc`) survives, and while one runs the core keeps running for
  it; otherwise the core is stopped and the op waits until it is gone.
  With the core not answering its socket, hc may still keep the city's
  records: it keeps them across a core restart, finished, and one left
  behind would refuse gc's next start of its name (`fresh_only`, exit 73)
  while every read of the stopped city answers it absent. So while the
  pack keeps an incarnation's metadata (it does until the record is
  removed), `server-stop` starts the core, holding the kick lock, and stops
  the city with it as above. A core that cannot be started, or a core of
  the city listening on another socket (`core.lock`: run
  `gc herdr-core restart-core`), is reported and leaves the city unparked,
  so reads kick the core back. Whatever the core, its programs may still
  run under their holders (`herdr-core hold --socket <session>.holder.<id>.sock`),
  so the process table is scanned: each incarnation is found by the pid
  and start time its metadata keeps (with the boot they count from: on
  Linux a start time counts clock ticks from boot, so one kept from
  another boot never names a process), as a city holder's program carrying
  its `GC_INSTANCE_TOKEN`, and by that token; its tree is ended, the token
  is scanned for again as `stop` does, and a holder left with no program
  is ended too. That sweep fences exactly as `stop`'s kill
  does, through the same fence and the same rescan: city infrastructure and
  any tmux server or client (with everything under it) is never signalled,
  so a tmux server founded from inside a box, its panes, and another
  city's tmux server carrying the token survive, while a tmux server the
  box's program runs under (hc's core started from a pane) fences none of
  that program's tree. The one exception to the fence is the city's own
  idle holders, matched by their exact `hold --socket` argv with the
  city's socket prefix: they are ended directly (a holder is never a tmux
  or infrastructure process). Exit 0 means the
  city's core is gone (or kept only for a foreign terminal) and no program
  of the city's sessions runs, so a second call exits 0; exit 1 names what
  may survive: a process that outlives its kill or cannot be read, a
  record whose metadata cannot be read, a process table that cannot be
  read, a holder that runs a process that cannot be read (or a program
  while an incarnation's metadata names neither its pid nor its instance
  token), an incarnation's program the fence keeps (a box whose program is
  a tmux client: only the core can end it), a core that runs but does not
  answer, one that answers but fails, one that cannot be started while hc
  may keep the city's records, a core of the city listening on another
  socket, or a start of the core in flight that does not finish in time.
- **A stopped city stays stopped.** When `server-stop` stops the core
  itself, it first marks the city parked (`parked.json` in the city's pack
  state); so does a `server-stop` that finds the core already down and
  no incarnation's metadata kept. While the mark is there, no read starts the core again, and with
  no holder or core process of the city left every read answers an empty
  city: `inventory` complete and empty, `observe` absent, `list-running`
  empty, `is-running`, `process-alive` and `is-attached` `false`, `peek`
  exit 66. That is what gc's stop confirmation and `gc status` read after
  a stop. It is the truth: nothing of the city runs, and only `start`
  brings the core back (every record of the city was ended and removed
  first, so that start's `fresh_only` finds no record of the name). A start clears the
  mark first, before it tries the core: one whose core then fails to
  start leaves the city unparked, and reads kick again as for any core
  that is down. The mark holds only while nothing of the core runs. gc
  never sends a start for a session it reads unknown, so a parked city
  with a holder still running would be stranded: `server-stop` clears the
  mark at its end when a holder or core process still runs (a core kept
  for what runs is not parked), and a read that finds one parked anyway
  (a `server-stop` killed at its deadline) answers unknown and kicks the
  core back to adopt it. `server-stop` holds the kick lock throughout, so
  a kick in flight finishes first and none starts the core while it
  sweeps. A core that ends without `server-stop` (a crash, a reboot) is
  not parked, and a read kicks a start as before.
  With the core down and nothing of it running, `is-running` and
  `process-alive` answer `false` and `stop` ends what the metadata still
  names, parked or not, without starting a core.
- **Not implemented**: `exec`, `provision` and `check-image` (exit 2 without
  reading stdin), `program-status` and session events.

## Input outcomes

How each answer from hc reads as gc's outcome words (gascity
`docs/reference/exec-session-provider.md`, "Typed input outcomes"). It needs
a gc that reads `carrier.ops` and `input-outcome`; an older gc sees exit 0
for a delivery and an ordinary failure for exit 80.

| hc's answer | Ops | Outcome | Exit |
|---|---|---|---|
| `send` typed, and the program went `working` (`started: true`) | `nudge` | `delivered` | 0 |
| `send` typed into a program that never reports OSC 7501 status (`started: null`) | `nudge` | `delivered` (as tmux's fire-and-forget `send-keys`) | 0 |
| `send` typed into a program that reports status but did not go `working` in hc's window (`started: false`) | `nudge` | `delivered_unobserved` | 0 + line |
| `send` written whole, then no reply: hc still holds it at the op's deadline (a person keeps typing), or the reply was lost | `nudge` | `delivered_unobserved` | 0 + line |
| `keys` or `interrupt` answered (whatever the interrupt observed) | `send-keys`, `interrupt` | `delivered` | 0 |
| the box's incarnation is intact (hc keeps no scrollback to clear) | `clear-scrollback` | `delivered` | 0 |
| no record carries the name; its newest record is finished or broken (a kept terminal's replacement shell, a lost holder); hc answers `not_found` or `finished` | all four | `gone` | 80 |
| `blocked`: the program waits on its own question | `nudge` | `pending_interaction` | 80 |
| `status_mismatch` | `nudge` | `busy` | 80 |
| `unavailable`: the terminal is starting or waits for a shell | all four | `not_sent` | 80 |
| the request never reached hc, or reached it cut short (hc acts on no part of a request) | all four | `not_sent` | 80 |
| the core is down (no socket, refused, no connection in time) | all four | `unavailable` | 80 |
| a tmux key with no herdr-core spelling (nothing is sent) | `send-keys` | `rejected` | 80 |
| nudge text that is not UTF-8 (hc's JSON cannot carry it; nothing is sent) | `nudge` | `rejected` | 80 |
| a request written, then no reply (timeout or lost connection) | `send-keys`, `interrupt`, `clear-scrollback` | unknown: a retried Esc or Ctrl-C can end the program | 1 |
| the core is a version the pack does not drive (`needs_update`, `unsupported_generation`, `incompatible`, a refused hello) | all four | unknown, "hc version unsupported: run gc doctor" | 1 |
| any other hc error kind | all four | unknown, naming the kind | 1 |

A `nudge` whose request reached hc whole is delivered: hc types a send only
once a person stops typing and finishes it after the pack stops waiting, so
a nudge still held at the op's deadline, or whose reply was lost, is typed
later, and gc's queue never sends it twice. The pack keeps no record of
sends. **Accepted limit:** a nudge hc still holds is lost if the core dies
before the person stops typing (rare). gc's nudge queue itself is
at-least-once: a gc process that dies mid-op redelivers after its claim's
lease (about two minutes) runs out, and a send hc holds for a person's pause
widens that window to the op's whole budget. A nudge stops waiting for hc
5 s before its deadline, so its answer reaches gc before gc gives up on the
op. `detail` is at most 1 KiB, one line, and redacted like stderr.

Under `conformance-faults` the pack injects `GC_RPP_FAULT` at its hc calls,
so every op takes its real path: `unavailable` (every call fails before
anything is written), `blocked` (the core refuses a `send` as `blocked`),
`lose_reply` and `hold_send` (an input call, and `clear-scrollback`'s
`terminal.get`, is done and its reply dropped, as a lost connection or a
send held past the deadline) and `dead` (every record reads finished).

## Foundations

- **One dispatch for every transport.** A handler gets an `OpRequest` (op,
  args, stdin, an env snapshot, a cancel token, a deadline, a redactor) and
  returns an `OpResult`. The per-op runner builds requests from argv and the
  process environment; handlers never read the environment themselves, so a
  long-lived transport can build the same requests and get the same answers.
  Only ops that take stdin read it, so `exec`, `provision` and `check-image`
  exit 2 without reading the tmux commands gc's carrier pipes to them.
- **Deterministic discovery.** Every gc process of a city (supervisor, CLI,
  cron, ssh, sudo) must find the same core. The city key is the raw
  `GC_EXEC_CITY_PATH` (`GC_CITY_PATH` for doctor and pack commands), or the
  fixed bucket `unscoped` when it is unset: never the cwd. The city id is
  `sha256(machine + "\0" + key)`, where `machine` is what herdr-core itself
  keys a machine on: `/etc/machine-id`, or on macOS the hardware UUID
  (IOPlatformUUID, read in process). Only when `/etc/machine-id` is missing,
  empty or `uninitialized` does it fall back to D-Bus's copy and then to
  `uname -n`, a last resort because machines get renamed; an id file that
  exists but cannot be read fails the call. The hc session is `gc-` plus 10
  hex digits of `sha256(city id + "\0" + R)`, so every state root gets its own
  core and sockets. All state lives under `R`: `GC_EXEC_STATE_DIR`, else
  `<password-database home>/.local/state/gc-runtime-herdr-core`, with its
  parents resolved so every spelling of one root names one core. `R` is a
  0700 directory owned by the user (a symlink or another owner's directory is
  refused). The caller's `XDG_*`, `HOME`, `TMPDIR`, `HC_SOCKET` and
  `HC_SESSION` are ignored, and nothing is written under the city path. A
  socket path too long for `sun_path`, counting the
  `<session>.holder.<8hex>.sock` sockets hc binds beside it
  (herdr-core `crates/herdr-core/src/paths.rs`), moves to
  `/tmp/gc-herdr-core-<uid>/`.
- **Deadlines.** An op's deadline is `GC_EXEC_DEADLINE_MS` when gc sends it
  (no gc release does yet), else gc's own timeout for the op (30 s; 120 s for
  start; 4 s for observe and is-attached). Every inner wait ends at least
  1 s before it.
- **The hc client.** One plain-mode connection per call, and every
  connection opens with the core's hello, gated (generation 1, at least the
  policy's minimum version) before the call is written on it: a core
  restarted or upgraded between two calls, idle or not, is gated before it
  is sent anything. A fixed per-call timeout table, cut by the deadline
  (`send` gets the deadline less 2 s). A connection dropped during the
  hello is retried once, as are `get`, `list` and `read` when it drops
  before the reply; nothing else ever. Every failure carries `written`:
  whether the request may have reached the core, which tells a driving op
  whether hc may still type what it sent.
- **stderr** is `"<op>: <message>"`, redacted: sensitive-key values (gc's
  markers) of 4 bytes (UTF-8) or more, every session-env value of 8 bytes
  (UTF-8) or more, `GC_INSTANCE_TOKEN` always, and secret-looking
  assignments. Tracebacks appear only under `GC_HERDR_CORE_DEBUG=1`,
  redacted too.

## Tests

The unit tier never builds, installs or runs a real herdr-core (its
holder-loss sweep can kill unrelated processes). Every hc conversation is
with fake-hc: a stdlib JSON-RPC server on a real Unix socket whose programs
are real child processes in their own sessions. Every reply it sends and
every request the client makes is checked against `hc.openrpc.json`,
vendored at the pinned tag (`tests/fakehc/hc.openrpc.provenance.json`).

From this directory, with the CI tool pins in any Python 3.9+ environment
kept outside the repository:

```bash
python -m pip install mypy==1.19.1 pytest==8.4.2 jsonschema==4.25.1 types-jsonschema==4.25.1.20251009
python -m pytest tests/unit -q
python -m mypy --config-file mypy.ini                       # the 3.9 floor
python -m mypy --config-file mypy.ini --python-version 3.12
GC_HC_SCHEMA_FETCH=1 python -m pytest tests/unit/test_fakehc_schema.py -q   # network: vendored == tag
```

gc's own checks of the runtime, against fake-hc run as the hc binary (a gc
build on `PATH` or in `GC_BIN`; `PYTHON` is an interpreter with
`jsonschema`, for fake-hc):

```bash
GC_BIN=/path/to/gc PYTHON=python tests/conformance.sh --json
```

It runs `gc runtime check` and `gc runtime conformance` and fails unless
every requirement passes or is skipped and the report is v2-ready. All state
goes to a scratch `GC_EXEC_STATE_DIR`; `--default-root` (CI only) proves the
default state root instead. Without `--json` it reads the text report, for a
gc that cannot encode it.

CI runs all of this in the `runtime-herdr-core` job on Python 3.9 and 3.12,
with gc pinned to a gascity commit, and the unit tier again in the shared
pytest step.

When the hc pin moves, re-vendor `tests/fakehc/hc.openrpc.json` from the new
tag and update its provenance file; the network check then proves the copy.
