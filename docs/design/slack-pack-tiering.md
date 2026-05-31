# slack-pack tiering: tier contracts, migration paths, and import compatibility

Design memo for `gc-yrw` (slack-pack tiering). Tracking bead: `gc-yrw.1`.

Status: design. Defines the contract that drives the extraction work in
`gc-yrw.2` (slack-mini), `gc-yrw.3` (slack-mini docs), `gc-yrw.4`
(slack-channel), and `gc-yrw.5` (retitle current pack → slack-full).

## Motivation

A reviewer on gastownhall/gascity-packs PR #8 asked: *"why does plugging in
Slack take 156 files?"* The honest answer is that the current pack is
**Tier 3** — a workspace-grade orchestration surface (webhooks, modals, file
uploads, peer fanout, multi-rig, room launcher) where roughly half the file
count is tests plus the gc convention of three command-wrapper files per verb.

But the question exposes a real adoption-friction problem: nobody wiring up
"`@mayor` in Slack" for the first time wants to opt into all 156 files. Tiering
lets a consumer adopt the smallest surface that fits their use case instead of
taking the whole integration or none of it.

This memo is **docs-only**. It defines what is IN and OUT of each tier, how a
city migrates between tiers, and whether tiers can coexist. It does not extract
any code — that is the job of the sibling beads.

---

## 1. Tier contracts

Three tiers. Each **strictly subsumes** the prior: every capability in Tier N
is present in Tier N+1. Migration up is additive (drop in the larger pack);
migration down requires re-deriving state and is not officially supported (see
§2).

```
Tier 1 — slack-mini       ~12-18 files     "Talk to mayor from Slack"
Tier 2 — slack-channel    ~50-60 files     "Bind your team channel to your session graph"
Tier 3 — slack-full       ~156+ files      "Workspace-grade multi-rig orchestration surface" (current pack)
```

### Tier 1 — slack-mini

**Use case:** add a bot to your company Slack, `@mayor` it from any channel, get
threaded replies.

**In:**
- Slack Events API receiver, only `app_mention`.
- Inbound bridge-mail path: mention → `gc mail send mayor`.
- One outbound verb: `gc slack post-message` (workspace-token-authed).
- 4 env vars (bot token, signing secret, workspace_id, city_name).

**Out:** bindings, registries, per-session identity, non-mention channels,
modals, files, fanout, multi-rig.

**Files:** ~12–18.

### Tier 2 — slack-channel

**Use case:** a team has a `#ops` channel; bind it to mayor (and optionally PL).
Team conversations route to the bound sessions, and sessions post back.
Per-session identity overrides let different agents post as different bot
personas.

**Tier 1 + adds:**
- Channel binding registry (channel ↔ N sessions, on-disk JSON).
- Verbs: `bind-dm`, `bind-room`, `publish`, `publish-to-channel`,
  `reply-current`, `identity`, `react`, `handle-alias` (cross-channel
  address-by-handle).
- Identity registry (display name + avatar overrides).
- Non-mention channel message routing to bound sessions.
- Basic inbound modal-button ack.

**Out:** multi-rig, peer fanout, room launcher, channel-name patterns, file
uploads, double-handle dispatch.

**Files:** ~50–60.

### Tier 3 — slack-full (current pack)

**Use case:** a workspace orchestrates a multi-rig session graph; channels map
to rigs map to session pools; peers fan out replies; cross-channel handles;
file uploads; room launcher (`@@<handle>` spawns a session); slash-command verb
intake.

**Tier 2 + adds:** rig binding, channel-name pattern resolver, room launcher
mode, handle aliases (double-handle dispatch), peer fanout, file upload,
`import-app` + `sync-commands`, and `status` / `retry-peer-fanout` / `map-rig`
diagnostics.

**Files:** ~156 (159 in the current snapshot on `main`). This is the pack that
lands at gastownhall/gascity-packs PR #8; `gc-yrw.5` retitles it to
`slack-full`.

---

## 2. Migration paths

### Up — additive, no state loss

Up-migration is a pack swap. Because each tier strictly subsumes the prior, the
larger pack reads the same on-disk registries the smaller pack wrote; existing
state is preserved and new capabilities light up.

**`slack-mini` → `slack-channel`:**
1. Replace the pack (`slack-mini` → `slack-channel`) in the city. Both register
   `name = "slack"`, so this is a swap, not a coexistence (see §3).
2. The bot token, signing secret, and workspace_id env vars carry over
   unchanged.
3. New on-disk registries (channel mappings, identities, handle aliases) start
   empty; `bind-dm` / `bind-room` / `identity` populate them. No mini state is
   invalidated — mini wrote none.

**`slack-channel` → `slack-full`:**
1. Replace the pack (`slack-channel` → `slack-full`).
2. Carries over: the channel-mappings, identity, and handle-alias registries
   written under Tier 2 are read unchanged by Tier 3.
3. New, initially-empty registries: apps (`import-app`), rig mappings
   (`map-rig`), room-launch mappings (`enable-room-launch`).
4. The adapter picks up the new registries on next start (or `SIGHUP`); Tier-2
   bindings keep working throughout.

In both directions up, the only required action is the pack swap plus
populating the newly available registries. No migration script is needed.

### Down — not officially supported; orphaned state documented

Down-migration is **not officially supported**. The smaller pack does not read
the larger pack's extra registries, so that state becomes orphaned (it persists
on disk but is ignored, and the verbs that wrote it no longer exist). Document,
don't auto-delete — silently deleting a consumer's registry data on downgrade
would be a destructive surprise.

**`slack-full` → `slack-channel`** orphans:
- `apps.json` — the apps registry (`import-app` records: OAuth client id,
  signing secret, bot-token linkage). Slack app remains installed
  workspace-side; only the local record is orphaned.
- `rig_mappings.json` — rig bindings (`map-rig`).
- `room_launch_mappings.json` — room-launch mappings (`enable-room-launch`).
- Peer-fanout queue / retry state, if any is persisted.

**`slack-channel` → `slack-mini`** orphans:
- `channel_mappings.json` — channel bindings (`bind-dm` / `bind-room` /
  `map-channel`).
- `identities.json` — per-session identity overrides (`identity`).
- `handle-aliases.json` — cross-channel handle → session-id aliases
  (`handle-alias`).

Recommended downgrade procedure (manual, by the operator): stop the adapter,
archive the orphaned `*.json` files out of the adapter state directory, swap the
pack, restart. Re-upgrading later requires re-deriving the archived state (the
files can be restored if their schema has not changed across versions, but this
is best-effort, not a supported contract).

---

## 3. Import compatibility

### Can a city import both `slack-mini` and `slack-channel` (or any two tiers)?

**No.** All three tiers register the same pack name in `pack.toml`:

```toml
[pack]
name = "slack"
```

Pack names must be unique within a city. If a city installs two packs that both
declare `name = "slack"`, only one wins — gc does not merge them and does not
namespace them apart. The `gc slack <verb>` surface, the `[[service]]` named
`slack`, and the `/svc/slack/*` reverse-proxy route all key off that single
name. Two packs claiming it is a collision, not a composition.

This is intentional: the tiers are **alternatives**, not **layers you stack at
install time**. The subsumption relationship (§1) is a *design-time* guarantee
that up-migration is additive — it is not an invitation to install more than
one tier simultaneously.

### Recommended pattern: one slack pack per city

Exactly **one**. A city picks the tier that matches its use case and installs
only that pack. To change tiers, swap the pack (§2) — never run two side by
side. The single `name = "slack"` namespace is the mechanism that enforces this:
the verb surface, the service, and the proxy route are all singular by
construction.

(If a future use case genuinely needs two independent Slack surfaces in one
city — e.g. two workspaces — that would require per-pack name parameterization,
which is out of scope for this tiering and tracked separately if it ever
arises.)

---

## 4. Verb surface per tier

Each `gc slack <verb>` is introduced by exactly one tier and inherited by all
higher tiers. The table maps every one of the **17 current Tier-3 verbs** to the
tier that introduces it.

| `gc slack <verb>`     | Introduced at | Purpose                                                        |
| --------------------- | ------------- | -------------------------------------------------------------- |
| `post-message`        | Tier 1        | Outbound workspace-token-authed message (the only mini verb).  |
| `bind-dm`             | Tier 2        | Bind a DM channel to one or more sessions.                     |
| `bind-room`           | Tier 2        | Bind a channel/room to one or more sessions.                   |
| `publish`             | Tier 2        | Publish a message from the current session to its bound target.|
| `publish-to-channel`  | Tier 2        | Publish to a specific channel.                                 |
| `reply-current`       | Tier 2        | Reply in the current inbound thread context.                   |
| `identity`            | Tier 2        | Set per-session display-name / avatar identity override.       |
| `react`               | Tier 2        | Add an emoji reaction to a message.                            |
| `handle-alias`        | Tier 2        | Register cross-channel handle → session alias.¹                |
| `map-channel`         | Tier 3        | Channel-name pattern → binding resolver.                       |
| `map-rig`             | Tier 3        | Bind a channel/pattern to a rig (multi-rig).                   |
| `enable-room-launch`  | Tier 3        | Enable `@@<handle>` room launcher mode.                        |
| `import-app`          | Tier 3        | OAuth app intake; populates the apps registry.                 |
| `sync-commands`       | Tier 3        | Push slash-command definitions to Slack.                       |
| `upload`              | Tier 3        | File upload to a channel/thread.                               |
| `retry-peer-fanout`   | Tier 3        | Re-drive a failed peer-fanout dispatch (diagnostic).           |
| `status`              | Tier 3        | Cross-registry status report (apps, channels, rigs).           |

Tier 1: 1 verb. Tier 2: +8 verbs (9 total). Tier 3: +8 verbs (**17 total**).

> ¹ **`handle-alias` tier boundary.** The `gc-yrw` contract lists `handle-alias`
> under Tier 2's verbs ("cross-channel address-by-handle") while also listing
> "handle aliases / double-handle dispatch" under Tier 3's additions. The
> resolution adopted here: the **`handle-alias` verb and single cross-channel
> handle resolution are Tier 2**; **double-handle dispatch** (addressing via two
> chained handles) is the **Tier 3** behavior layered on the same registry.
> Tier 2's explicit "Out" list excludes "double-handle dispatch," which confirms
> this split. See Open Questions (§7).

---

## 5. Service shape per tier

All tiers run the adapter as a gc `proxy_process` service named `slack` (UDS for
`/publish` + `/healthz`, public TCP for `/slack/events`). What differs is the
on-disk registry state the adapter and CLI maintain.

The current pack has **6 registries** (4 written by `gc slack` CLI commands and
read by the adapter on start / `SIGHUP`, plus identity and handle-alias):

| # | Registry             | File                        | CLI writer                    |
| - | -------------------- | --------------------------- | ----------------------------- |
| 1 | Apps                 | `apps.json`                 | `gc slack import-app`         |
| 2 | Channel mappings     | `channel_mappings.json`     | `gc slack map-channel` / `bind-*` |
| 3 | Rig mappings         | `rig_mappings.json`         | `gc slack map-rig`            |
| 4 | Room launch mappings | `room_launch_mappings.json` | `gc slack enable-room-launch` |
| 5 | Identity             | `identities.json`           | `gc slack identity`           |
| 6 | Handle aliases       | `handle-aliases.json`       | `gc slack handle-alias`       |

(The adapter also maintains a `thread_sessions.json` runtime map of inbound
threads → sessions. That is auto-managed adapter state, not an operator-
configured registry, so it is excluded from the "6 registries" count and is
present wherever inbound routing is — i.e. Tier 2+.)

**Tier 1 — slack-mini:** minimal `proxy_process`, bot-token-only, **no UDS state
registries**. The adapter receives `app_mention`, bridges to `gc mail send
mayor`, and the single outbound verb posts via workspace token. No on-disk
registry files.

**Tier 2 — slack-channel:** `proxy_process` + on-disk **channel/identity**
registries. Concretely, the three Tier-2 registries are **channel mappings (2),
identity (5), and handle aliases (6)** — channel binding, per-session identity
override, and cross-channel handle resolution. Inbound non-mention routing and
the `thread_sessions` runtime map appear here.

**Tier 3 — slack-full:** full `proxy_process` + **all 6 registries** + room
launcher + peer fanout. Tier 3 adds the **apps (1), rig mappings (3), and
room-launch mappings (4)** registries on top of Tier 2's three, plus peer-fanout
dispatch and the `@@<handle>` room launcher.

| Registry             | Tier 1 | Tier 2 | Tier 3 |
| -------------------- | :----: | :----: | :----: |
| (none)               |   ✓    |        |        |
| Channel mappings     |        |   ✓    |   ✓    |
| Identity             |        |   ✓    |   ✓    |
| Handle aliases       |        |   ✓    |   ✓    |
| Apps                 |        |        |   ✓    |
| Rig mappings         |        |        |   ✓    |
| Room launch mappings |        |        |   ✓    |

---

## 6. Test surface per tier

The current Tier-3 pack snapshot on `main` carries **~43 test files** (32 Go
`*_test.go` + 11 Python) against 33 Go source files, plus 51 command-wrapper
files (17 verbs × the 3-file gc convention: `<verb>.sh` + `command.toml` +
`help.md`). Roughly half the pack's 159 files are test or boilerplate — which is
the grounded answer to "why 156 files."

Test-count expectations below are budgets for the extraction beads, not hard
counts; the principle is **each tier ships the tests for its own surface and
inherits the lower tiers' tests unchanged**.

| Tier | Test budget (approx.) | What is covered |
| ---- | --------------------- | --------------- |
| Tier 1 — slack-mini | ~6–10 test files | Events-API signature verification; `app_mention` parse; mention → `gc mail send mayor` bridge; `post-message` outbound; env-var validation / startup config. |
| Tier 2 — slack-channel | Tier 1 + ~12–18 | Channel-mapping registry read/write + SIGHUP reload; identity registry; handle-alias resolution (single handle); non-mention inbound routing to bound sessions; modal-button ack; the 8 Tier-2 verbs' CLI surface. |
| Tier 3 — slack-full | Tier 2 + remainder (~43 total today) | Apps registry + OAuth callback; rig dispatch + rig mapping + rig workdir; room-launch mapping + launcher; peer fanout + `retry-peer-fanout`; channel-name pattern resolver; file upload; double-handle dispatch; `import-app` / `sync-commands`; `status` cross-registry view. Includes the Python adapter integration tests. |

**Layer coverage:** unit tests live beside each registry and resolver
(`*_test.go` next to the source); the Python `tests/` directory holds adapter
integration tests (webhook → bridge → outbound round-trips). Tier 1 and Tier 2
extractions must carry the subset of each that exercises only their surface;
Tier 3 keeps the full set.

---

## 7. Open questions

1. **`slack-channel`: derived-from-Tier-3 or designed-fresh?**
   **Recommendation: designed-fresh** (build Tier 2 on top of the Tier-1
   kernel, per `gc-yrw.4`), *not* carved down from Tier 3. Rationale: Tier 3's
   code assumes multi-rig dispatch, peer fanout, and the apps registry
   throughout its routing and state paths; carving those out leaves dead
   branches and defensive `if registry == nil` guards that erode the module.
   Designing Tier 2 fresh against the Tier-1 kernel yields a clean ~50–60 file
   pack whose every branch is exercised. The cost is some re-implementation of
   channel routing, but that routing is simpler without the Tier-3 assumptions.
   This decision is **deferred to `gc-yrw.4`** for final confirmation but the
   memo recommends designed-fresh.

2. **`handle-alias` tier boundary** (see §4 footnote). The source contract is
   ambiguous: `handle-alias` is listed under both Tier 2 verbs and Tier 3
   additions. Adopted resolution: **verb + single-handle resolution = Tier 2;
   double-handle dispatch = Tier 3.** Confirm against the Tier-2 extraction
   whether single-handle resolution can stand alone without pulling in fanout.

3. **Thread-session runtime state.** `thread_sessions.json` is adapter-managed
   runtime state, not an operator registry. It appears wherever inbound routing
   exists (Tier 2+). Confirm Tier 2 needs it (it does, for `reply-current`
   thread context) and that Tier 1 can omit it entirely (mini replies in-thread
   directly from the inbound event without persisting a map).

4. **Down-migration support.** This memo documents down-migration as
   unsupported with orphaned-state archival (§2). Open: whether to ship a
   best-effort `gc slack migrate-down` helper that archives orphaned registries
   automatically, or leave it fully manual. Current recommendation: manual,
   documented — a helper risks the silent-deletion failure mode.

5. **Two Slack surfaces in one city.** Out of scope for tiering (§3). If a
   genuine multi-workspace use case arises, it needs per-pack name
   parameterization, tracked separately.
