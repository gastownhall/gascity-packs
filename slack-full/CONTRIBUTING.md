# Contributing to slack-full

slack-full is the Slack provider extension for Gas City that lives at
`slack-full/` in the
[`gastownhall/gascity-packs`](https://github.com/gastownhall/gascity-packs)
repository. Open pull requests against that repository; every path below is
relative to its root.

## Build flow

Three pieces ship with this pack:

- **Pack scripts** live in `scripts/` and are pure Python. They run via the
  `gc slack <command>` shims under `commands/` and have no compile step.
- **Adapter** (the Slack-side HTTP/UDS bridge) is the Go binary whose source
  lives at `adapter/main.go` (colocated with the pack). It is its own Go
  module so it can travel intact when the pack is mirrored upstream.
- **Operator CLI** (`gc-slack-cli`) is the second Go binary that backs the
  `gc slack <cmd>` verb surface (import-app, map-channel, map-rig,
  post-message, sync-commands, enable-room-launch). Source lives at
  `cli/main.go` + `cli/cmd/`; like the adapter it is its own Go module so
  it can travel intact upstream.

Build the adapter with:

```bash
cd slack-full/adapter
go build -o gc-slack-adapter
```

In deployed packs you normally don't build by hand: the `[[service]]`
command is `adapter/run.sh`, which rebuilds `gc-slack-adapter` from
source whenever the binary is missing (build artifacts are gitignored,
so `gc import install` re-materializes the pack cache without them —
run.sh self-heals instead of stranding the service).

Build the operator CLI with:

```bash
cd slack-full/cli
go build -o gc-slack-cli .
```

The pack's `commands/<cmd>.sh` wrappers exec `$GC_PACK_DIR/cli/gc-slack-cli`,
so the CLI binary must live at that path — i.e. inside the installed pack's
`cli/` subdirectory — when operators invoke `gc slack <cmd>`.

## Test flow

Run pack tests (pytest, no external deps beyond `pytest` itself):

```bash
pytest slack-full/tests/
```

Run adapter tests:

```bash
cd slack-full/adapter
go test -race ./...
```

Run CLI tests:

```bash
cd slack-full/cli
go test -race ./...
```

CI runs all three on every PR (see the pack tests and the "Run Slack full
adapter tests" and "Run Slack full CLI tests" steps in
`.github/workflows/ci.yml`).

## Secret handling

slack-full reads Slack credentials from environment variables only. Never
commit `.env` files or tokens. The README's "Adapter env contract" section
documents the full env-var contract; use a `.env` file outside the repo or a
secret manager and source it before running adapter / scripts.

## Pull requests

- Keep PRs scoped to slack-full (or paired adapter changes when needed).
- Update `CHANGELOG.md` for any user-visible change — add bullets under a
  new `[Unreleased]` section, and the next release tag promotes them.
- Run `pytest`, `go test -race ./...` in `adapter/`, and
  `go test -race ./...` in `cli/` locally before opening the PR.
