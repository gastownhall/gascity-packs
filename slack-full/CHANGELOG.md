# Changelog

All notable changes to slack-full (formerly slack-pack) are documented in
this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A retaken Slack redelivery whose channel leg already reached gc
  skips `postInbound` and retries only the failed alias leg (codex
  r12): core does not consume `dedup_key`, so the old
  forget-the-whole-event recovery duplicated the bound session's
  turn. The completed leg is remembered next to the event-dedup entry
  (TTL-bounded, cleared on commit) before `forget` wakes the parked
  retry.
- The launcher alias is reserved BEFORE the first-message POST and
  rolled back if that POST fails (codex r13): a user's `@handle`
  follow-up processed during the multi-second first post used to miss
  the alias lookup and fall to the channel-bound path — which the
  launcher session is not on — losing the follow-up. The rollback
  runs before the event's dedup claim is released, so a woken
  redelivery re-enters the launcher path (re-posting the remainder)
  instead of the pre-claimed alias branch.
- Busy-reaction clears are now attributed to the publishing agent
  (codex r11): each mark records the parsed target handle, and a
  delivered reply consumes only marks whose handle resolves (via the
  handle-alias registry) to the publishing session — so when M1
  targets agent A and M2 re-targets agent B in the same thread, A's
  late reply can no longer strip B's pending hourglass. Marks with no
  recorded handle, an unregistered handle, or an unattributable
  publisher clear unconditionally, preserving the prior behavior.
- Launcher alias bootstrap no longer hijacks a handle onto another
  handle's thread session (codex r9): the thread-session registry
  records which `@@handle` created each binding (persisted; absent on
  pre-existing records), and the unclaimed-handle alias bootstrap on
  thread reuse fires only for the same handle (the codex r8 retry
  case) — a different `@@handle` converging on an existing thread
  still posts into that session but is not globally alias-bound to
  it.
- Busy-reaction lifecycle (hq-xizo, ported from
  `feat/hq-xizo-slack-full-hardening`): a targeted inbound gets a busy
  reaction (`BUSY_REACTION`, default `hourglass`; set-but-empty
  disables) added on dispatch and removed when the agent's reply
  publishes back into the same conversation/thread, tracked in a
  bounded in-memory registry keyed by (conversation, thread key) with
  a 30-minute TTL. Replaces the prior unconditional `eyes` reaction on
  targeted inbounds; the ⚠️ dispatch-failure reaction stays. `/react`
  gains an optional `remove:true` issuing `reactions.remove`
  (`no_reaction` treated as benign delivery, mirroring
  `already_reacted`), surfaced on the CLI as `gc slack react
  --remove`. Beyond the original hq-xizo commit, the removal is
  ordered after the corresponding `reactions.add` completes (a fast
  reply otherwise races the in-flight add and the busy emoji sticks
  forever) and a threaded `/publish-file` reply clears the mark
  exactly like a text publish. A thread-reply inbound is marked under
  both its thread root AND its own ts — reply-current and the
  alias-dispatch instructions thread replies under the inbound's own
  ts, which the root-only key missed. A channel-root reply (the
  documented default `gc slack reply-current` shape, no thread ts)
  clears every pending mark in the conversation, and re-targeting a
  thread before the first reply lands removes the displaced message's
  reaction instead of stranding it. The mark registers before the
  forward to gc (a reply can arrive before postInbound even returns;
  a failed forward cancels the mark before releasing the event's
  dedup claim and restores any marks the failed inbound displaced),
  displaced-mark reactions are removed only after the displacing
  forward succeeds, and a re-mark of the same message merges
  add-completion channels so a remove waits for every in-flight add
  (the wait bound exceeds the Slack client timeout, so ordering
  provably holds). Registry entries carry displaced-ancestor
  reactions across overlapping failed re-targets (deduplicated,
  bounded per entry) so every added emoji stays clearable; displaced
  marks are retired only once the event's FINAL delivery succeeds
  (the alias POST when one fires, postInbound otherwise) and restored
  if it fails — unless a reply consumed the thread while the dispatch
  was in flight (consumed keys are tombstoned; blocked marks get
  their reactions removed instead of being re-parked unclearably);
  and a failed cross-channel alias delivery removes its own busy
  emoji next to the ⚠️ — synchronously, before any parked retry
  wakes — instead of stranding it. Note the lifecycle fires only when an agent target
  is
  parsed from the message (`@handle:` prefix, User Group mention, or
  sticky thread handle) — plain messages that reach a session solely
  through a channel binding carry no parsed target and get no busy
  reaction, by design. (hw-94w5k finding #3)

### Fixed

- Slack Events API redeliveries are now deduplicated on `event_id`
  with a 10-minute seen-set: Slack retries any delivery it considers
  unacknowledged and each retry re-forwarded the same message into the
  bound session as a duplicate notification (observed as
  byte-identical inbound log pairs). Entries are two-state
  (in-flight → committed): a redelivery racing the first delivery's
  still-running forward parks (slot released, no dispatch-semaphore
  starvation) until the owner's verdict — commit drops it, forget
  hands it the event — and never gives up: it already returned a 200,
  so Slack will not resend it. The wait runs in a goroutine after the
  handler has returned, so Slack's ack is never delayed behind it.
  Adapter→gc forwards run on a 20-second-timeout client and Slack Web
  API calls on 30s/120s-timeout clients so claims always conclude,
  and a take-over blocks for dispatch capacity instead of dropping
  the event's last copy on a full queue. For targeted inbounds the alias dispatch
  owns the verdict (success commits, failure forgets). Deliveries
  dropped at the queue-full boundary are never recorded, and a failed
  forward releases its id, so a Slack retry can always recover the
  message. Redeliveries of known events are routed past the
  queue-full load-shed (a parked wait needs no dispatch slot), so a
  saturated queue can never discard the only remaining copy of an
  in-flight event. Transient `@@handle` launcher failures (spawn or
  first-message forward) forget the claim like every other forward
  failure — the launcher alias registers only after a first message
  lands (on any attempt, including a retry that re-acquired the
  thread session), so a retry re-enters the launcher instead of
  dead-ending in the pre-claimed branch; terminal launcher outcomes
  (delivered, user-error ephemerals) commit. (hw-94w5k finding #4)
- `openBeneath` (the confined open backing `/publish-file`) restores
  the old per-component no-follow guarantee on top of `os.Root`
  (which follows a symlink at the root argument and resolves in-root
  symlinks at every component, ignoring `O_NOFOLLOW` for them): the
  root is pre-opened with `O_NOFOLLOW|O_DIRECTORY` and
  identity-matched against the `os.Root` handle, every intermediate
  component is Lstat'd (symlink → hard failure) and descended into
  via a pinned sub-root whose identity must match, and the leaf is
  Lstat'd + inode-pinned — so a raced-in link anywhere on the path
  fails instead of substituting a different (even in-root) file.
- Human file posts delivered with subtype `file_share` are no longer
  discarded by the system-noise subtype gate, and file-only posts (no
  caption) are no longer discarded by the empty-text gate — both now
  reach the attachment download pipeline. Other subtypes
  (`message_changed`, `bot_message`, …) and bot-authored file posts
  stay filtered. (hw-94w5k finding #1)
- `gc slack react` / `reply-current` latest-inbound lookup now matches
  `target_session` against every identifier the session is known by
  (id, `GC_SESSION_NAME`, gc-reported alias/session_name), not just
  `GC_SESSION_ID`. Name-bound sessions produce inbound events carrying
  the NAME, so the id-only match made the default `--current` mode
  bail with "no recent inbound transcript entry" right after an
  inbound landed. The ambient `GC_SESSION_NAME` only joins the match
  set when the requested session IS the current one — an explicit
  `--session <other>` never inherits it. (hw-94w5k finding #2)

### Changed

- Renamed the pack directory from `slack-pack/` to `slack-full/` and the
  `pack.toml` name from `slack` to `slack-full` as part of the Slack pack
  tiering split (`gc-yrw`). This pack is now **Tier 3** of the Slack
  family; the smaller [slack-mini](../slack-mini) (Tier 1) and
  [slack-channel](../slack-channel) (Tier 2) packs were extracted from it.
  The user-facing verb surface (`gc slack <cmd>`) and the registered
  `slack` service name are unchanged — only the catalog directory and pack
  name moved, so there is no collision with `slack-mini` / `slack-channel`.
  See the [tiering design memo](../docs/design/slack-pack-tiering.md) and
  the README "Tiering" section for the decision tree. (`gc-yrw.5`)
- Moved CLI commands (`gc slack import-app`, `map-channel`, `map-rig`,
  `sync-commands`, `enable-room-launch`, `post-message`) from the gc
  binary into a new in-pack Go module at `examples/slack-pack/cli/`
  (module `github.com/sjarmak/gc-slack-cli`). User-facing surface
  (`gc slack <cmd>`) is unchanged — pack wrappers under
  `commands/<cmd>.sh` exec the new binary at
  `$GC_PACK_DIR/cli/gc-slack-cli` so operator command-line ergonomics
  stay identical to the pre-relocation gc-binary verbs. The pack now
  ships two Go binaries (adapter + cli), each in its own go.mod;
  `gc slack status` continues to dispatch to the existing Python
  implementation under `scripts/slack_chat_status.py`. Build flow
  documented in [CONTRIBUTING.md](./CONTRIBUTING.md#build-flow).
  (`gc-coe10`)

### Added

- `gc slack retry-peer-fanout` — operational recovery for peer-fanout.
  Walks recent `extmsg.peer_fanout_failed` events (added in this change
  too), filters by `--since` / `--conversation` / `--max`, deduplicates
  against successful `extmsg.peer_fanout_retried` events, and re-issues
  each notification via the new
  `POST /v0/city/<cityName>/extmsg/peer-fanout/retry` endpoint with a
  small cooldown between attempts. The endpoint emits an
  `extmsg.peer_fanout_retried` audit event per attempt with the
  `original_seq`, so re-running on the same set is a no-op
  (`gc-cby.7`).
- SIGHUP-driven reload for the four CLI-written registry files
  (`apps.json`, `channel_mappings.json`, `rig_mappings.json`,
  `room_launch_mappings.json`). Operators can now run
  `gc slack import-app`, `gc slack map-channel`, `gc slack map-rig`, or
  `gc slack enable-room-launch` and signal the adapter with
  `pkill -HUP gc-slack-adapter` (or any other SIGHUP delivery) to pick
  up the new bindings without a service restart (`gc-cby.23`). Reload is
  all-or-nothing across the four registries — a single parse failure
  aborts the cycle with the live state untouched. A missing file is a
  no-op (preserves state); operators clear by writing an empty `{}`
  document, NOT by `rm`.

### Changed

- The trailing reminder printed by `gc slack map-rig`,
  `gc slack map-channel`, and `gc slack enable-room-launch` now leads
  with the SIGHUP path (`pkill -HUP gc-slack-adapter`) and offers
  `gc service restart slack` as the fallback, since SIGHUP avoids the
  startup gap.
- Adapter Go source relocated from `examples/oversight-rig/adapter/`
  to `examples/slack-pack/adapter/` (`gc-28a`). The pack is now
  self-contained for upstream extraction into a separate
  `gascity-packs` repo. No behavioral change; the binary path
  (`examples/slack-pack/adapter/gc-slack-adapter`) is unchanged, so
  the supervised `proxy_process` service picks up the new build at
  next restart with byte-identical functionality.
- Build flow simplified to a single command:
  `cd examples/slack-pack/adapter && go build -o gc-slack-adapter`.

### Security

- Default adapter state under `/tmp/gc-slack-adapter/*` is no longer
  world-readable on shared hosts (`gc-ywe.6`). Concretely: the
  identity registry, handle-alias registry, and inbound file store now
  create directories with mode `0o700` and files with mode `0o600`
  (previously `0o755`/`0o644`). Pre-fix installs are migrated on
  startup by a one-shot tightener that walks the three configured
  store paths and chmods only-if-strictly-looser; setuid, setgid, and
  sticky bits are preserved so operator-customized layouts (e.g.
  setgid for shared-group access) survive intact. Operators who
  deliberately set tighter perms (e.g. `0o400` read-only) are also
  left alone. As defense-in-depth, the proxy_process Unix domain
  socket is chmod'd to `0o600` after bind on top of its
  `0o700` controller-managed parent directory at
  `/tmp/gcsvc-<uid>/<hash>/`.

## [0.1.0] - 2026-05-03

Initial preview. Feature-by-feature port of the upstream `discord` pack
shape; today's surface is enough to run a multi-session oversight loop
end-to-end (DMs, rooms, peer fanout, identity overrides, bidirectional
file attachments).

### Added

- `gc slack bind-dm` — bind a Slack DM channel to one named session.
- `gc slack bind-room` — bind a room to multiple sessions, with
  `--enable-peer-fanout`, `--allow-untargeted-publication`,
  `--max-peer-triggered-publishes`, `--max-total-peer-deliveries`,
  `--default-handle`, `--handle HANDLE=SESSION`, and
  `--binding-owner`.
- `gc slack reply-current` — reply to the latest Slack event in the
  current session, routed through gc's `/extmsg/outbound` so transcript
  recording and peer fanout fire (`--via adapter` keeps the direct path
  for diagnostics).
- `gc slack publish` — publish to a session's saved binding (target
  session required, no event-scan fallback).
- `gc slack publish-to-channel` — publish to an arbitrary channel ID
  with no session binding required.
- `gc slack status` — read-only diagnostics over adapters, bindings,
  and recent traffic. Supports `--session SID`, `--since`, and
  `--json`.
- `gc slack react` — add an emoji reaction to a Slack message.
- `gc slack identity` — register and unregister per-session
  `chat:write.customize` identities so each bound session posts under
  its own persona.
- `gc slack handle-alias` — register and unregister cross-channel
  `@handle` to session-id aliases used by the address-by-handle
  protocol.
- `gc slack upload` — bidirectional file attachments
  (`/publish-file` outbound, auto-download of inbound files into
  `$INBOUND_FILE_STORE/<channel>/<ts>-<filename>`, scrubbed by an
  in-process retention janitor).
- `template-fragments/slack-v0.template.md` — composable prompt
  fragment for any agent in a slack-bound session.
- Pack-owned intake service (`[[service]]` proxy_process) supervising
  the adapter via UDS for `/publish`, with the public Slack webhook
  still terminating at adapter TCP `:8775`.
- Native `SessionID` field on `PublishRequest` (replacing the prior
  metadata workaround).
- Scope banner and host-agnostic README copy for upstream-prep
  readiness.
- Adapter env contract documented in the package docstring and in the
  pack README, categorized as must-set / optional-override /
  controller-injected / consumer-specific.

### Changed

- **Breaking (standalone deployments only):** `GC_CITY_NAME` is now
  required. The adapter previously fell back to a hardcoded city name
  when the env var was unset, silently routing inbound traffic to the
  wrong destination. Any standalone (`run.sh`-style) deployment must
  set `GC_CITY_NAME` explicitly. `proxy_process`-supervised deployments
  are unaffected as long as the env file sourced before `gc start`
  defines it.

### Provenance

This release was developed in-tree at `examples/slack-pack/` (with the
adapter at `examples/oversight-rig/adapter/`). Key gascity commits:

- `cfd6d7de` — initial Slack extmsg adapter (Path B).
- `8495e4d7` — pack scaffold + `bind-dm` + `reply-current`.
- `4aa07108` — `bind-room` with peer-fanout policy plumbing.
- `39d92543` — route `reply-current` through `gc /extmsg/outbound`.
- `c1e1f6a1` — adapter UDS mode + `[[service]]` proxy_process
  (`gc-5rz` Phase A).
- `111641dd` — `gc slack status` read-only diagnostics.
- `3edeb3d0` — `gc slack publish` to session bindings.
- `b8abb72d` — identity DELETE + bidirectional file attachments + new
  commands.
- `bfd64511` — native `SessionID` in `PublishRequest`, drop metadata
  workaround (`gc-kvt`).
- `010bc588` — strip host-specific references and add scope banner
  (`gc-ywe.1`, `gc-ywe.4`).
- `3db27544` — document adapter env contract and remove the
  `ds-research` `GC_CITY_NAME` fallback (`gc-ywe.2`).

[0.1.0]: https://github.com/gastownhall/gascity/commits/main/examples/slack-pack
