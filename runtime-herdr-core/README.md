# runtime-herdr-core

A Gas City **runtime pack**: runtime `herdr-core` runs agent sessions in
[herdr-core](https://github.com/herdrdev/herdr-core) (`hc`), the terminal
daemon the Herdr desktop app is built on. The pack ships one executable that
speaks the Runtime Provider Protocol (RPP v0). It is typed Python, standard
library only, Python 3.9 or later, so it needs no binary of its own.

## Status: observe.v1 ops in, not released

The executable implements gc's lifecycle and observe.v1 ops on herdr-core
and is v2-ready: it declares `observe.v1`, `report-attachment`,
`report-activity`, `city-scoped` and `conformance-faults` (locality
`local`), and passes
`gc runtime check` and `gc runtime conformance` against fake-hc (see
[Tests](#tests)). It cannot run a configured agent yet: the agent launcher,
which applies the session environment, staging, setup commands and the
first turn without handing secrets to hc, and the driving ops (`nudge`,
`send-keys`, `interrupt`) are the next change, so `start` refuses a start
config that needs them. The pack is not in `registry.toml` yet: it is published
once it has run real cities on a pinned herdr-core. The doctor checks and
the `gc herdr-core install|status|upgrade|restart-core` commands are not in
this build: until they are, install herdr-core 0.1.19 yourself at
`<home>/.local/share/gc-runtime-herdr-core/hc/0.1.19/herdr-core`, or name a
binary in the city's pack config (`hc_bin` in `<R>/pack/<city id>/config.json`).
A `herdr-core` or `hc` on `PATH` is never used.

The runtime is named `herdr-core`, never `herdr`: `herdr` is a gc builtin,
and declaring it is a composition error (RUNTIME-SEL-007).

## Layout

```text
runtime-herdr-core/
  pack.toml                        [runtimes.herdr-core] -> assets/bin/gc-runtime-herdr-core
  mypy.ini                         mypy --strict; disallow_any_expr in rpp/ and herdrcore/
  assets/
    bin/gc-runtime-herdr-core      0755, #!/usr/bin/env -S python3 -I -S
    gc_runtime_herdr_core/
      main.py                      argv dispatch; the only reader of os.environ
      handshake.py                 the capabilities this build declares
      rpp/                         provider-neutral RPP kit
        exitcodes.py wire.py ops.py perop.py cancel.py redact.py flock.py
        statedir.py jsonval.py
      hc/                          herdr-core client
        paths.py version.py client.py types.py parse.py errors.py
      herdrcore/                   runtime semantics
        ops_table.py context.py config.py core.py command.py naming.py
        records.py metastore.py procs.py attach.py activity.py reads.py
        lifecycle.py
  tests/
    fakehc/                        hc double (in process, or as a herdr-core binary) + vendored schema
    unit/                          the unit tier
    conformance.sh                 gc runtime check + gc runtime conformance against fake-hc
```

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
  most one at a time and none for five minutes after a failed start.
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
  removes it, and a plain `start` replaces it.
- **Start** runs the command under `sh -c` with the core's environment, in
  `work_dir` (which must exist; the home without one); hc gets only `TERM`. **Stop** and **kill-object** end the program with
  `terminal.kill` and remove the record and its metadata.
- **Activity.** A program that never reported OSC 7501 status is active
  when its screen changes: `inventory` and `get-last-activity` read the
  screen of each such running agent (hc keeps no output time).
- **Attachment.** hc counts no viewers; a box is attached while the pack's
  `attach` runs (it holds a lock) or a `herdr-core|hc attach` process of this
  user targets it on this city's core. `is-attached` exits 1 when it cannot
  tell, including when such a process's environment cannot be read.
  `attach` checks the core answers first and runs `hc attach` with the
  core's allowlist environment, so it never starts a core on gc's.
- **Not implemented**: `exec`, `provision` and `check-image` (exit 2 without
  reading stdin); the driving ops, `watch-startup` and `copy-to` (exit 2,
  until the launcher lands); `server-stop`, `program-status` and session
  events.

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
