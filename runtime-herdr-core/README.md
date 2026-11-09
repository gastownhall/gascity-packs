# runtime-herdr-core

A Gas City **runtime pack**: runtime `herdr-core` runs agent sessions in
[herdr-core](https://github.com/herdrdev/herdr-core) (`hc`), the terminal
daemon the Herdr desktop app is built on. The pack ships one executable that
speaks the Runtime Provider Protocol (RPP v0). It is typed Python, standard
library only, Python 3.9 or later, so it needs no binary of its own.

## Status: scaffold, not released

This is the scaffold: the layers the runtime is built on, namely the RPP
kit, the hc client, the fake-hc test double and CI. The executable answers
`protocol` (version 0, no capabilities, locality `local`) and `x-version`;
**every session op answers exit 2 ("unknown operation") until the runtime
ops land**. The pack is not in `registry.toml` yet: it is published once the
runtime ops are in and proven on a real city. Do not select
`provider = "herdr-core"` yet.

The runtime is named `herdr-core`, never `herdr`: `herdr` is a gc builtin,
and declaring it is a composition error (RUNTIME-SEL-007).

## Layout

```text
runtime-herdr-core/
  pack.toml                        [runtimes.herdr-core] -> assets/bin/gc-runtime-herdr-core
  mypy.ini                         mypy --strict; disallow_any_expr in rpp/
  assets/
    bin/gc-runtime-herdr-core      0755, #!/usr/bin/env -S python3 -I -S
    gc_runtime_herdr_core/
      main.py                      argv dispatch; the only reader of os.environ
      rpp/                         provider-neutral RPP kit
        exitcodes.py wire.py ops.py perop.py cancel.py redact.py flock.py
        statedir.py jsonval.py
      hc/                          herdr-core client
        paths.py version.py client.py types.py parse.py errors.py
  tests/
    fakehc/                        in-process hc double + vendored schema
    unit/                          the unit tier
```

## What this scaffold fixes in place

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
  keys a machine on: `/etc/machine-id` (then D-Bus's), or on macOS the
  hardware UUID (IOPlatformUUID, read in process); `uname -n` only when no id
  is readable, because machines get renamed. The hc session is `gc-` plus 10
  hex digits of `sha256(city id + "\0" + R)`, so every state root gets its own
  core and sockets. All state lives under `R`: `GC_EXEC_STATE_DIR`, else
  `<user home>/.local/state/gc-runtime-herdr-core` (the home the user
  database gives, never `$HOME`), with its parents resolved so every spelling
  of one root names one core. `R` is a 0700 directory owned by the user (a
  symlink or another owner's directory is refused). The caller's `XDG_*`, `HOME`, `TMPDIR`, `HC_SOCKET` and
  `HC_SESSION` are ignored, and nothing is written under the city path. A
  socket path too long for `sun_path`, counting the
  `<session>.holder.<8hex>.sock` sockets hc binds beside it
  (herdr-core `crates/herdr-core/src/paths.rs`), moves to
  `/tmp/gc-herdr-core-<uid>/`.
- **Deadlines.** An op's deadline is `GC_EXEC_DEADLINE_MS` when gc sends it
  (no gc release does yet), else gc's own timeout for the op (30 s; 120 s for
  start; 4 s for observe and is-attached). Every inner wait ends at least
  1 s before it.
- **The hc client.** One plain-mode connection per call; a fixed per-call
  timeout table, cut by the deadline (`send` gets the deadline less 2 s);
  `hello`, `get`, `list` and `read` retried once when a connection drops,
  nothing else ever; the core gated on its hello (generation 1, at least the
  policy's minimum version) and re-gated after any lost connection. Every
  failure carries `written`: whether the request may have reached the core,
  which tells a driving op whether hc may still type what it sent.
- **stderr** is `"<op>: <message>"`, redacted: sensitive-key values (gc's
  markers), every session-env value of 8 characters or more,
  `GC_INSTANCE_TOKEN` always, and secret-looking assignments. Tracebacks
  appear only under `GC_HERDR_CORE_DEBUG=1`, redacted too.

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

CI runs the same in the `runtime-herdr-core` job on Python 3.9 and 3.12, and
the unit tier again in the shared pytest step.

When the hc pin moves, re-vendor `tests/fakehc/hc.openrpc.json` from the new
tag and update its provenance file; the network check then proves the copy.
