# Phase 1 porting contract — slack-cli relocation

This document is the autonomous-execution contract for every Phase 1
leaf of the `gc-coe10` slack-cli relocation. Every leaf ports one
`gc slack <cmd>` verb from `cmd/gc/cmd_slack_<cmd>.go` into
`examples/slack-full/cli/cmd/<cmd>.go` and registers it on the
cobra root in `examples/slack-full/cli/main.go`.

Phase 0 stood up the new module skeleton (`gc-wj70y`) and copied the
shared state helpers (`gc-nqy49`). Phase 1 leaves now copy
verb-specific code and re-point it at the new helpers; Phase 2 deletes
the originals once every verb has cut over.

## Source → Target file mapping

| Phase 1 source (read-only)                | Phase 1 target (new)                                 |
| ----------------------------------------- | ---------------------------------------------------- |
| `cmd/gc/cmd_slack_<cmd>.go`               | `examples/slack-full/cli/cmd/<cmd>.go`               |
| `cmd/gc/cmd_slack_<cmd>_test.go`          | `examples/slack-full/cli/cmd/<cmd>_test.go`          |
| `cmd/gc/main.go` cobra registration       | `examples/slack-full/cli/main.go` cobra registration |

The `cmd/gc/` originals stay UNTOUCHED through every Phase 1 leaf —
Phase 2 cutover deletes them all at once after every verb has been
ported and verified.

## Package layout

- Each command file uses `package cmd`. (If a leaf chooses to split
  a long verb into a per-command subpackage instead, document that
  choice in the leaf's commit body. Keep it consistent within the
  leaf — don't mix the two in one verb's port.)
- Constructor pattern (exported, capitalized for cross-package import
  from `main.go`):
  ```go
  func New<Cmd>Cmd(stdout, stderr io.Writer) *cobra.Command
  ```
  This mirrors the existing `cmd/gc/newSlack<Cmd>Cmd(stdout, _ io.Writer)`
  shape so the body copies cleanly. If the original took only `stdout`
  (e.g. `newSlackMapChannelCmd`), the ported version still accepts both
  to keep the registration call site uniform; pass `_` to drop the
  unused writer.
- The `RunE` body and the helper `run<Cmd>` function copy verbatim
  from `cmd/gc/`, with only the import substitutions below applied.

## Import substitutions (mechanical)

Apply these renames at port time. They are pure text substitutions —
no behavior changes:

| Old import / identifier (cmd/gc)                              | New import / identifier (slack-cli)                                    |
| ------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `"github.com/gastownhall/gascity/internal/citylayout"`        | not imported — see "City paths" below                                  |
| `slackAppRegistry` / `newSlackAppRegistry` / `slackAppRecord` | `apps.Registry` / `apps.NewRegistry` / `apps.Record` (`internal/state/apps`)  |
| `slackAppsRegistryPath`                                       | `apps.Path` (`internal/state/apps`)                                    |
| `slackAppKey`                                                 | `apps.Key`                                                             |
| `slackAppLogView` / `slackAppJSONView`                        | `apps.LogView` / `apps.JSONView`                                       |
| `safeLogFields()` / `safeJSONFields()`                        | `SafeLogFields()` / `SafeJSONFields()` (methods on `apps.Record`)      |
| `sanitizeForLog`                                              | `apps.SanitizeForLog` (gc-cby.13 deny-list helper)                     |
| `slackChannelMappingRegistry` / `newSlackChannelMappingRegistry` / `slackChannelMappingRecord` | `channels.Registry` / `channels.NewRegistry` / `channels.Record` (`internal/state/channels`) |
| `slackChannelMappingsPath`                                    | `channels.Path`                                                        |
| `slackChannelMappingKey`                                      | `channels.Key`                                                         |
| `slackChannelMappingTargetKindRig` / `slackChannelMappingTargetKindSession` | `channels.TargetKindRig` / `channels.TargetKindSession`     |
| `slackRigMappingRegistry` / `newSlackRigMappingRegistry` / `slackRigMappingRecord` | `rigs.Registry` / `rigs.NewRegistry` / `rigs.Record` (`internal/state/rigs`) |
| `slackRigMappingsPath`                                        | `rigs.Path`                                                            |
| `slackRigMappingKey` / `slackRigChannelKey`                   | `rigs.Key` / `rigs.ChannelKey`                                         |
| `slackRoomLaunchMappingRegistry` / `newSlackRoomLaunchMappingRegistry` / `slackRoomLaunchMappingRecord` | `rooms.Registry` / `rooms.NewRegistry` / `rooms.Record` (`internal/state/rooms`) |
| `slackRoomLaunchMappingsPath`                                 | `rooms.Path`                                                           |
| `slackRoomLaunchMappingKey`                                   | `rooms.Key`                                                            |
| `slackBlock` / `slackBlockText`                               | `blockkit.Block` / `blockkit.BlockText`                                |
| `slackStatusKind` / `slackStatusKindMilestone` / etc.         | `blockkit.StatusKind` / `blockkit.StatusKindMilestone` / etc.          |
| `slackStatusPayload` / `slackStatusField` / `slackStatusItem` / `slackStatusProgress` | `blockkit.StatusPayload` / `.StatusField` / `.StatusItem` / `.StatusProgress` |
| `renderStatusBlocks`                                          | `blockkit.RenderStatusBlocks`                                          |
| `slackWorkspaceIDEnv`                                         | `workspace.IDEnv` (`internal/state/workspace`)                         |
| `slackWorkspaceIDDefault()`                                   | `workspace.IDDefault()`                                                |
| `slackWorkspaceIDFlagUsage`                                   | `workspace.IDFlagUsage`                                                |

### City paths

The `cmd/gc/` originals built every disk path through
`citylayout.RuntimePath(cityPath, "slack", <file>)`. The `slack-cli`
module ships its own per-registry `Path()` helpers — each subpackage
bakes in `<cityPath>/.gc/slack/<file>.json`, so consumers call:

```go
apps.Path(cityRoot)              // <cityRoot>/.gc/slack/apps.json
channels.Path(cityRoot)          // <cityRoot>/.gc/slack/channel_mappings.json
rigs.Path(cityRoot)              // <cityRoot>/.gc/slack/rig_mappings.json
rooms.Path(cityRoot)             // <cityRoot>/.gc/slack/room_launch_mappings.json
```

These are subpackage-private helpers, NOT a shared top-level import —
the slack-cli module deliberately stays free of `internal/citylayout`
coupling so the slack-pack remains a self-contained example. If a
Phase 1 verb needs an arbitrary slack-rooted path that doesn't match
any registry, inline `filepath.Join(cityRoot, ".gc", "slack", parts...)`
in the verb file rather than reaching for a shared helper.

### City-root resolution

The `cmd/gc/` originals get `cityPath` from the gc CLI's
`citylayout.WorkingCity(cwd)` walk-up. The slack-cli has no such
helper. Every Phase 1 verb that needs `cityPath` should accept it via
a `--city` flag (default: walk up from `cwd` looking for `.gc/`) OR
via a `GC_CITY_PATH` env var. Settle the resolution policy in the
first Phase 1 leaf that touches it (likely `enable-room-launch` or
`import-app`); subsequent leaves reuse the same resolver helper.
Keep the helper in `examples/slack-full/cli/cmd/citypath.go` and
export it as `cmd.ResolveCityPath(...)`.

## What NOT to change in Phase 1

- **`cmd/gc/cmd_slack_<cmd>.go`** — the originals are the safety net
  while we cut over. Phase 2 deletes them; Phase 1 leaves them
  byte-identical.
- **`cmd/gc/main.go`** subcommand registration — keep the gc CLI
  serving `gc slack <cmd>` from the original code path until every
  verb is ported.
- **`examples/slack-full/commands/*.sh`** wrappers — the pack still
  invokes `gc slack <cmd>` through the gc binary. Phase 2 will rewrite
  these to call `gc-slack-cli <cmd>` after the cutover.
- **`pack.toml`** — same reasoning. Pack-level wiring changes are
  Phase 2 work.
- **`examples/slack-full/cli/internal/state/`** — the helpers landed
  in `gc-nqy49` and are frozen for Phase 1. If a leaf hits a missing
  helper, file a follow-up bead under `gc-coe10` rather than mutating
  the internal-state surface mid-relocation.

## Phase 1 leaf acceptance criteria template

Every Phase 1 leaf MUST satisfy ALL of these before close:

- `examples/slack-full/cli/cmd/<cmd>.go` compiles
  (`cd examples/slack-full/cli && go build ./...` is green)
- `examples/slack-full/cli/cmd/<cmd>_test.go` passes
  (`go test -race ./cmd/...` is green)
- `cd examples/slack-full/cli && go vet ./...` clean
- `gofmt -l examples/slack-full/cli/cmd/` reports no diffs
- `examples/slack-full/cli/main.go` registers the new subcommand under
  `gc-slack-cli <cmd>` via a single `rootCmd.AddCommand(...)` line
  (see "Cobra subcommand registration" below)
- `cmd/gc/cmd_slack_<cmd>.go` (the original) is untouched
  (`git diff cmd/gc/cmd_slack_<cmd>.go` is empty)
- Top-level `go test ./cmd/gc -run "TestSlack..."` still PASS
  (the original tests still exercise the original code path)
- Behavior parity verified by reading both files side-by-side:
  same flags, same defaults, same output formatting, same error
  messages, same exit codes. Where renames change identifier names
  in error strings (e.g. `slackAppRecord` → `apps.Record`), match
  the cmd/gc wording verbatim.

## Cobra subcommand registration in main.go

Each Phase 1 leaf appends ONE line to `examples/slack-full/cli/main.go`
inside `newRootCmd()`:

```go
cmd.AddCommand(cmdpkg.NewEnableRoomLaunchCmd(os.Stdout, os.Stderr))
cmd.AddCommand(cmdpkg.NewImportAppCmd(os.Stdout, os.Stderr))
// ...
```

Where `cmdpkg` is the local alias for
`github.com/sjarmak/gc-slack-cli/cmd` (the new subpackage holding
verb implementations).

Conventions:
- **Alphabetical order** by command name. Keeps the file diff-stable
  and gives merges a deterministic sort key.
- **One line per leaf.** Each Phase 1 leaf adds exactly one
  `cmd.AddCommand(...)` line. If two leaves race on this file, merge
  resolution is trivial (accept both lines, sort alphabetically).
- The leaf that lands the very first verb also creates
  `examples/slack-full/cli/cmd/` and adds the `cmdpkg` import to
  `main.go`. Subsequent leaves only add the `AddCommand` line.

## Common helpers checklist

The import map below is authoritative for which `internal/state/`
subpackages each verb depends on. Use it to size each Phase 1 leaf
and to confirm the leaf's `import` block before opening its commit.

| Verb                 | Subpackages imported                              | Notes                                                              |
| -------------------- | ------------------------------------------------- | ------------------------------------------------------------------ |
| `enable-room-launch` | `workspace`, `rooms`                              | `--workspace-id` flag (workspace), `rooms.Registry` for the bind   |
| `import-app`         | `workspace`, `apps`                               | `--workspace-id` flag, `apps.Record` + `apps.Registry`, prints `apps.Record.SafeLogFields()` |
| `map-channel`        | `workspace`, `channels`, `rigs`                   | rigs only for the cross-store conflict check (rig owns this channel?) |
| `map-rig`            | `workspace`, `channels`, `rigs`                   | channels only for the cross-store conflict check (channel already mapped per-channel?) |
| `post-message`       | `blockkit`                                        | Pure HTTP client beyond rendering — no city-rooted state.          |
| `status`             | `apps`, `channels`, `rigs`                        | Reads all three registries; emits `apps.JSONView` for `--json`.    |
| `sync-commands`      | `workspace`, `apps`                               | `--workspace-id` flag, `apps.Registry` to read the manifest record |

The original `cmd/gc/cmd_slack_status.go` defines a wrapper struct
`slackStatusRigMapping` that adds a `Conflict` field on top of
`slackRigMappingRecord`. That wrapper is **status-local** — it lives
in `cmd/<verb>.go` after porting (renamed `StatusRigMapping`), NOT in
`internal/state/rigs/`. Phase 1 keeps verb-local helper types in
the verb file.

## Out of scope for Phase 1

- Cutting `pack.toml` over to invoke `gc-slack-cli` — Phase 2.
- Deleting `cmd/gc/cmd_slack_*.go` and `cmd/gc/slack_*.go` originals
  — Phase 2.
- Updating `examples/slack-full/commands/*.sh` wrappers — Phase 2.
- Adding new flags or commands not present in the cmd/gc original —
  out of scope; file a follow-up bead under `gc-coe10`.
- Refactoring the verb's logic — pure structural copy with renames
  only. If a Phase 1 leaf finds a bug in the cmd/gc original, fix it
  in BOTH places under a separate bead, not in the porting commit.
