# Slack Company Rooms

## Status

Draft v2 for review, 2026-07-17. Successor to the Discord company-rooms pilot
(accepted 2026-07-15, `discord/docs/company-rooms.md` on
`feat/discord-company-rooms`); targets the same end state on Slack
infrastructure with two scope changes: durable event admission is the
foundational layer rather than a later reliability patch, and per-agent DMs
are in final scope (delivered in a staged phase). v2 incorporates a
four-lens adversarial design review.

## Objective

Model Slack channels as visible company rooms. Most agents may be present in
a room, while only a configured subset wakes for ordinary human conversation.
Native Slack mentions of real per-agent bot users provide directed activation
across city boundaries.

Slack is the visible cross-city transport; it is not an authority or
credential broker. The design must remain portable to Gasworks/Crucible.

Every admissible company-room event is durably recorded and deduplicated
before the transport is acknowledged. Delivery is redrivable and
restart-safe; queue saturation is backpressure, never silent loss. Delivery
to sessions is at-least-once with receipt-side suppression — duplicates are
possible only in a narrow, documented crash window until the city-level
durable-request-ledger lands (Phase 5). Traffic outside imported company
rooms keeps the legacy pipeline unchanged.

## Terms

- **Switchboard**: the slack-full adapter's Slack app for a visibility
  boundary. It subscribes to room message events and is the single admission
  owner for company-room traffic.
- **Agent identity app**: a minimal Slack app for one named agent. Its bot
  user is the agent's real, mentionable `<@U…>` identity and its bot token is
  the agent's outbound sending identity. In the rooms phases it has no event
  subscriptions; the DM phase adds `message.im`.
- **Member**: a directory-listed agent that may be explicitly activated in a
  room. Membership does not cause the session to run for every message.
- **Ambient wake**: a member that receives a human message containing no
  native mention of a company agent.
- **Thread ambient wake**: a member whose authenticated agent identity has
  already posted in a thread and therefore receives later untagged human turns
  in that same thread.
- **Mention wake**: a member that receives a message whose native mention
  tokens include that member's registered bot user ID.
- **Delegation**: a visible, directed company-bot message created with
  `gc slack delegate` and durably correlated to its expected responder.
- **Result**: a visible threaded reply from the expected responder to a
  recorded delegation.
- **Receipt**: the durable ingress record created for an admissible
  company-room event before the HTTP acknowledgment to Slack.

## Topology

One switchboard app per visibility boundary receives every room event and
enforces routing exactly once. One agent identity app per named agent
provides the mentionable identity and outbound sender. A versioned company
directory binds names to Slack IDs and rooms to wake policy; a separate
company-bindings registry binds (room, agent) pairs to local sessions.

For roughly 16 agents this is ~17 installed apps. Slack Free caps custom
apps at 10 workspace-wide; on paid plans bots are not billed member seats
(Slack usage-limit and fair-billing help articles). A three-app pilot
(switchboard, two agents) fits a Free workspace if slots remain.

The switchboard model satisfies the durable-request-ledger drafts'
single-admission-owner constraint: per-agent apps observe nothing in rooms,
so one event stream exists per visibility boundary and one receipt per
message. If an enclave must not be visible to the shared switchboard, that
enclave gets its own switchboard app and directory.

## Membership and Provisioning

Slack delivers `message.channels` / `message.groups` events only for
channels the app's bot user has joined, and `chat.postMessage` into a
channel requires membership (private channels always; public unless
`chat:write.public`, which this design does not use so that private rooms
behave identically). Membership is therefore part of the room contract:

- The switchboard bot and every directory member's bot must be invited to
  each directory room. A directory room the switchboard has not joined
  produces zero events — an invisible failure unless surfaced.
- `gc slack import-company-directory` and `gc slack peers` verify
  switchboard membership per room (`conversations.info` /
  `conversations.members`; scopes `channels:read`, `groups:read` added to
  the switchboard manifest), best-effort and warnings-only. In Phase 1 the
  adapter does not re-verify membership on directory reload — reload-time
  verification is a Phase 2 addition; until then, re-running `peers` after
  membership changes is the check. The adapter's sole status surface is
  `/healthz` detail (there is no separate gateway status payload in this
  pack).
- Agent identity apps are provisioned from a manifest template: bot user,
  `chat:write`, App Home Messages tab enabled
  (`app_home.messages_tab_enabled: true`,
  `messages_tab_read_only_enabled: false` — required before the DM phase
  can work at all), no event subscriptions until the DM phase adds
  `message.im` + `im:history`. Provisioning harvests each `app_id` and
  `bot_user_id` into the directory TOML and registers each signing secret
  with the adapter's multi-secret verification.

## Directory Contract

The company directory is non-secret, versioned data imported into each city.
It is stored separately from mutable Slack app configuration (its own
registry file, not `apps.json`) so config commands cannot erase it. It
contains no tokens.

```toml
schema_version = 1

[[agents]]
name = "ollie"
app_id = "A0AAAAAA1"
bot_user_id = "U0AAAAAA1"

[[agents]]
name = "riley"
app_id = "A0AAAAAA2"
bot_user_id = "U0AAAAAA2"

[[rooms]]
name = "orchestrator-team"
team_id = "T0AAAAAAA"
channel_id = "C0AAAAAAA"
members = ["*"]
ambient_wake = ["ollie"]
mention_wake = ["*"]
```

Agent names and room names are lowercase stable slugs. `app_id`,
`bot_user_id`, room names, and `(team_id, channel_id)` pairs are unique. A
duplicate or unknown reference makes the directory invalid; routing fails
closed. `members = ["*"]` means all listed agents; `mention_wake = ["*"]`
means all members are mention-eligible; wildcards are forbidden in
`ambient_wake`. Wake lists must be subsets of members.

Delivery additionally requires a **singleton company binding**: the
company-bindings registry maps each (room, agent) pair to exactly one named
session, written by `gc slack bind-company-agent`. A binding may be
**city-qualified** (`--city`): the target session lives in a different gc
city on the same host — the switchboard remains the single admission
owner and delivers wakes to that city's supervisor API (configured via
`SLACK_COMPANY_CITY_APIS`), matching the live org's one-team-per-city
topology. A woken agent with no binding is a recorded delivery failure
for that target, never a legacy fallback. The directory cannot launch
arbitrary sessions.

The adapter keeps normalized in-memory snapshots of both registries. They
are staged and committed **outside** the existing six-registry atomic
reload: a valid replacement becomes the new snapshot; a malformed or
semantically invalid replacement is reported and the last-known-good
snapshot is retained, without blocking the other registries' reload (this
mirrors the Discord reference and preserves the isolation rationale). On a
cold start with a missing or invalid directory, company routing is empty
and the adapter keeps running — the load error is surfaced, legacy rooms
and DMs continue through their existing paths, and pending company receipts
are parked, not dropped.

## Durable Admission

This is the foundational layer. It applies to Slack Events API POSTs whose
`(team_id, channel_id)` matches an imported company room — and, in the DM
phase, per-agent DM conversations. All other traffic keeps the legacy
ack-first path byte-for-byte.

Order of operations for a company-room event POST:

1. Verify the Slack signature (existing multi-secret trial HMAC, ±5 min
   replay window, fail closed).
2. Synchronously decode the event envelope: outer `api_app_id`, `event_id`,
   `team_id`, and the full inner `event` object; capture
   `x-slack-retry-num` / `x-slack-retry-reason` from the request headers.
3. Admissibility gate — an explicit subtype allowlist: subtype absent,
   `file_share`, `thread_broadcast`, or `bot_message`. Everything else
   (`channel_join`, `channel_topic`, hidden edit/delete records,
   `url_verification` handshakes, unsupported event types) is acknowledged
   with HTTP 200 and creates no receipt. The switchboard's `app_mention`
   copies of company-room messages are likewise owned by the company path
   and acknowledged without a receipt — the `message.channels` copy is
   the canonical admitted event — so they never reach legacy dispatch. An event with no stable
   `(team_id, channel_id, ts)` identity is logged and dropped with HTTP
   200 — never 5xx, which would burn Slack's retry budget on an unkeyable
   event.
4. Compute the canonical origin key `(team_id, channel_id, ts)`. `ts` is
   unique per channel; the observing app is never a key input.
5. Look up the receipt store. A duplicate origin returns HTTP 200
   immediately; `x-slack-retry-num` redeliveries terminate here.
6. Create the receipt durably and atomically — claim and content in one
   step: the full receipt (including the complete inner event and outer
   identifiers, which later routing and crash replay require) is written
   to a temp file, fsynced, then hard-linked to its final origin-keyed
   name; `EEXIST` means duplicate. An existing-but-unparseable receipt is
   quarantined (`*.corrupt`) and the claim retried once. This is the
   admission linearization point; there is no window in which a claim
   exists without its content.
7. Return HTTP 200 — a local disk append fits far inside Slack's
   three-second budget.
8. If persistence fails, return HTTP 503 **without** `x-slack-no-retry`.
   Slack redelivers (~immediately, +1 min, +5 min). **Enabling the Delayed
   Events option on the switchboard app is a required operator step**: it
   extends redelivery to hourly retries for 24 hours, which is what makes
   a receipt-store outage recoverable rather than lossy. Residual loss
   windows remain and are accepted, documented risk: an outage longer than
   24 hours, or Slack auto-disabling the subscription (>95% failures over
   60 minutes at ≥1,000 events/hour — below that volume Slack does not
   auto-disable). The receipt store exposes a write-failure counter in
   `/healthz` detail; that counter is the paging hook, and the re-enable
   path (app config → Event Subscriptions) is part of the operator
   runbook. If the receipt store cannot be initialized at startup, the
   switchboard runs degraded: company-room admissible events receive 503
   (never legacy delivery) and `/healthz` reports the store error until
   the store recovers.
9. Routing and delivery proceed asynchronously after the acknowledgment.
   The wake set is computed once, at first delivery, and frozen into the
   receipt's per-target records under keys
   `ingress:<id>:target:<session>`; redrives drive the recorded targets
   and never recompute the route. Each session submission carries its key
   as an `Idempotency-Key` header. gc's idempotency cache is best-effort
   (in-memory, bounded TTL), so the durable receipt is the authority: a
   target is marked delivered only on gc's acknowledged acceptance;
   timeouts, 5xx, 408, and 429 stay pending for retry with the same key;
   a definitive 4xx marks the target failed with the response detail; and
   retries are bounded by an attempts cap (exhaustion is a terminal,
   visible failure). The overall guarantee is at-least-once with
   receipt-side suppression. True end-to-end exactly-once arrives with
   the ledger integration (Phase 5).
10. Dispatch saturation is backpressure: the receipt stays pending and the
    recovery sweep delivers it later. Nothing admitted is ever silently
    dropped. A receipt whose channel no longer matches any directory room
    (directory removed, shrunk, or failed to load) is **parked** — left
    pending with a recorded reason, retried by the sweep, never terminally
    resolved and never legacy-delivered.

The HTTP 200 is a transport receipt, not a visible acknowledgment. An
optional, config-gated visible ack adds a 👀 reaction after admission and
swaps it for ✅ on terminal completion or a concise ⚠️ reply plus receipt
ID on terminal failure. `reactions.add` returning `already_reacted` is
treated as success; `too_many_emoji` and similar caps degrade the ack
silently; the remove+add swap is best-effort cosmetic — the durable
receipt, not the emoji, is authoritative.

Startup recovery is a barrier scoped to the company path: legacy routes,
`/healthz`, interactions, and the internal publish listener serve
immediately; company-room events receive HTTP 503 (retryable) until one
synchronous scan of pending ingress receipts succeeds. Posting-intent
recovery is deliberately not part of the adapter barrier: outbound
intents are owned by the CLI side and reconciled lazily on every company
verb invocation (against the receipt store, never by reposting), with
stale intents surfaced on `/healthz` as the operator signal. `/healthz`
reports barrier state. The periodic sweep starts only after one full
success and waits one interval before its first scan.

Receipt states are pack-native (`received`, `routing`, terminal
`delivered` / `no_delivery` / `failed`, with parked-pending as a reason on
non-terminal receipts). The durable-request-ledger drafts use a different
taxonomy (`spooled → admitting → core_bound → terminal`); Phase 5 performs
an explicit state mapping — it is not a rename, and receipts here
deliberately retain the raw event body (the ledger's receipts do not, so
Phase 5 splits body storage into a spool-side store).

## Routing Contract

Native company-agent mentions are exclusive. They replace ambient routing
for that message; they do not add to it.

| Author and message | Sessions woken |
| --- | --- |
| Allowed human root, no native company-agent mention | The room's `ambient_wake` members |
| Allowed human thread reply, no native company-agent mention | The room's `ambient_wake` members plus authenticated prior agent participants in that thread |
| Allowed human, one or more native company-agent mentions | Only the mentioned, eligible members |
| Registered company bot, no native company-agent mention | Nobody |
| Registered company bot with native company-agent mentions | Only the mentioned, eligible members |
| Unknown bot, webhook/integration, or the switchboard itself | Nobody |

The native mention set of a message is the union of `<@U…>` user elements
in its `rich_text` blocks and canonical `<@U…>` / `<@U…|label>` tokens in
its top-level `text`, matched exactly against directory `bot_user_id`s.
Slack guarantees `rich_text` blocks only for end-user client messages;
bot-composed messages may carry mentions only as text tokens, so neither
source alone is sufficient. Plain text that merely resembles `@riley`
contains no canonical token and never wakes anyone; over-inclusion is
bounded because a matched ID still passes membership and
mention-eligibility checks. Multiple eligible mentions wake each named
receiver exactly once. The v0 delegation command emits one target per
message so requests and results remain individually correlated.

Thread participation is fail-closed and receipt-backed. An agent joins the
ambient reader set only after a bot-authored reply in that exact
`(team_id, channel_id, thread_root_ts)` passes the `bots.info` company-author
corroboration and the agent is a current room member. Unknown bots, raw
`user`/`app_id` claims, switchboard posts, root channel posts, and arbitrary
text cannot enroll a participant. Later untagged human replies retain the
configured room ambient set and add those participants with wake kind
`thread_ambient`; a native company-agent mention remains exclusive and adds no
thread readers. The verified author name is stored on the ingress receipt, so
participation survives adapter restarts and expires with receipt retention.

Plain text such as `riley` is intentionally not adapter-level addressing. A
thread participant or configured ambient reader receives that turn and applies
the agent response policy; an agent outside those reader sets must first be
introduced with a native Slack mention.

Author classification is fail-closed. A human author has a `user` ID, no
`bot_id`, and an allowlisted subtype (absent, `file_share`,
`thread_broadcast`). A bot author (`bot_message` subtype or `bot_id`
present) must resolve to exactly one registered agent via the documented
path — `bot_id` through a cached `bots.info` lookup to its `user_id`
(switchboard scope `users:read`), with the event's `user` field as
corroboration when present — and ambiguity delivers nothing. Workspace
webhooks and unregistered integrations are bot messages that resolve to no
agent: ignored. The switchboard's own posts are ignored except for
delegation-intent echo reconciliation.

Suppression is deterministic and adapter-side: the switchboard computes the
wake set from the directory and delivers only to sessions bound in the
company-bindings registry. Company rooms bypass the legacy path in which
the channel-bound session receives every message and is prompt-trusted to
stay silent. All room members may read the Slack transcript; agents that are
neither configured ambient readers, prior thread participants, nor mentioned
receive no session turn.

## Context Hydration

Slack is the canonical room transcript. A directed wake includes the
current message, the verified human root when one exists, and a bounded
excerpt of recent room messages fetched via `conversations.history` /
`conversations.replies`, limited by both count and encoded size, and
labeled untrusted. Failure to fetch history does not broaden routing or
trust; the current message is delivered with `context_status:
context_unavailable`, and a verified root is included when it can still be
fetched independently. The gateway hydrates only sessions actually woken.

## Trust and Authority

Trusted peer ingress requires all of the following:

1. The team and channel exactly match an imported company room and the
   switchboard's existing allowlist.
2. The author is a bot resolving to exactly one registered company agent
   (via `bot_id` → `bots.info` → `user_id` against the directory), with no
   webhook provenance.
3. The author is not the receiving agent.
4. The receiving agent's exact `bot_user_id` appears in the message's
   native mention set.
5. Both agents are room members, the receiver is mention-eligible, and the
   (room, receiver) pair has exactly one session in the company-bindings
   registry.

Peer input uses `kind: slack_peer_delegation` or `kind: slack_peer_result`;
it never enters the human-message or generic extmsg path. The body is
untrusted. The recipient applies its own charter and credential policy; a
peer cannot widen that charter, grant credentials, or claim human approval
transitively. The envelope keeps `peer_authority: peer_only` for every peer
turn and records human linkage separately as `root_provenance:
human_root_verified`; consumers must not collapse the two.

Slack has no `allowed_mentions` equivalent, so mention discipline is a
composition contract: company posts use top-level `text` only — never
`blocks`, never `link_names`, never `parse=full` (defaults only) — and
agent-supplied bodies are entity-escaped (`&`, `<`, `>`) before posting.
Under those constraints the service-constructed `<@target>` is the only
live mention in a delegation and the recorded requester the only live
mention in a result; bare `@channel` / `@here` / `#channel` text cannot
become live notifications because automatic parsing is never enabled.
Synthesis replies to the human root contain no live agent mentions.

## Command Contract

```text
gc slack import-company-directory --file <rooms.toml>
gc slack bind-company-agent --room <name> --agent <name> --session <name>
gc slack peers [--room <name>]
gc slack delegate --turn-ref <ref> --to <agent> --body-file <path>
gc slack delegate --turn-ref <ref> --cancel --to <agent>
gc slack reply-current --turn-ref <ref> --body-file <path>
```

`import-company-directory` validates and normalizes the TOML, verifies
switchboard room membership, and atomically replaces the directory
registry. `bind-company-agent` records the singleton (room, agent) →
session binding; rebinding replaces, and ambiguity is impossible by
construction. `peers` reports rooms, members, wake policy, bindings, and
membership warnings.

Each authenticated reminder carries the room name, team/channel id, origin
timestamp, human thread root, receipt id, and an opaque `turn_ref`. The
switchboard persists that turn under `company-current-turn/by-ref/` before
waking the agent; records are create-once and retained for the same seven-day
window as ingress receipts. The mutable per-session pointer remains only for
pre-rollout compatibility. Post-rollout `delegate` and `reply-current` fail
closed without the reminder's `--turn-ref`, then verify the referenced session,
agent binding, directory room route, and turn kind before posting. Thus another
room waking the same named session cannot redirect an in-progress reply or
delegation; agents never memorize IDs or tokens.
It durably persists a posting intent before the provider POST
(prepared → posting → published, bounded attempts, TTL), then posts
`<@target> …` as the delegating agent's identity app into the human root's
thread, carrying a content-addressed nonce in Slack message metadata
(`metadata.event_type: gc_delegation`, nonce in `event_payload`). The
delegation record — keyed by the posted `(channel, ts)` with the expected
responder's `bot_user_id` — is materialized before the CLI reports success.
Crash recovery reconciles unresolved intents against
`conversations.replies` **with `include_all_metadata=true`** (without it
Slack omits `event_payload` and reconciliation would miss every nonce);
reconciliation that cannot find the nonce parks the intent — it never
reposts on ambiguity, because `chat.postMessage` is not idempotent.
Metadata is a correlation breadcrumb only — workspace-visible and mutable;
the durable record remains authoritative and must also match responder,
workspace, channel, thread root, and recorded Slack `ts`.

On a peer delegation, the reminder's exact
`gc slack reply-current --turn-ref …` command posts the result into the
same human-root thread, mentioning only the recorded requester. Slack has
no nested replies, so a result cannot reference the delegation message
directly; correlation is by durable record. A claim requires the full
peer trust checklist plus: the message is in thread `thread_root_ts` and
authored by the expected responder; its native mentions include the
recorded requester; and its result metadata matches the record's nonce
and delegation `ts` — the metadata gate is load-bearing for claim
admission (a clarifying question or hand-typed post from the responder
delivers as ordinary peer input and consumes nothing), while authorship
remains the trust anchor, so metadata alone can never claim. `delegate`
enforces at most one pending delegation per `(team, channel,
thread_root_ts, responder, requester)` under a cross-process lock, and
the turn-bound `gc slack delegate --cancel` recovers a wedged tuple without waiting out
the TTL. On a peer result, the requester is directed back to the
verified human root without mentioning ambient or prior peer agents. An
unmatched reply is never an implicitly trusted result — potentially
in-flight references are parked for recovery, identifiable replies to
the switchboard itself are rejected, and other unmatched replies remain
ordinary peer input.

Multi-specialist synthesis keeps the Discord contract: the requester issues
every intended sibling delegation before waiting; result claims for the
same verified human root, requester session, app, and room are serialized
under one cross-process group lock; each claim freezes a synthesis snapshot
(compatible and responded counts, pending delegation identities,
`synthesis_ready`), and replay cannot rewrite a frozen snapshot. V0 allows
one delegation hop; a delegated recipient may return a result but may not
redelegate that turn. Self-targeting is rejected.

## Identities and Tokens

Outbound identity is real, not cosmetic: delegations and results are posted
with the acting agent's own bot token, so the message author *is* the
mentionable `<@U…>` identity. `chat:write.customize` display overrides
remain a legacy path for non-company rooms only.

Per-agent bot tokens live outside agent sandboxes in the adapter's secrets
directory, one file per agent (`secrets/bot-token-<agent>.txt`, 0600 in a
0700 directory), selected by the directory's agent name at posting time. In
Crucible, a city-owned Slack service holds token custody and sandboxes
submit typed delegate/reply requests only. The pilot uses long-lived
tokens; production enables Slack token rotation (rotated access tokens
expire every 12 hours) with the gateway refreshing automatically. OpenBao
references replace token files when the org manifest lands; the directory
never contains secrets either way.

## Per-Agent DMs

New scope relative to the Discord pilot, which deferred DMs. Delivered as
the final phase, after room parity.

- Each agent identity app subscribes to `message.im` (scope `im:history`)
  pointing at the same public events endpoint, with its App Home Messages
  tab enabled (a hard Slack prerequisite for humans to DM a bot).
- Signature verification for app-attributed events binds the claimed app:
  the adapter resolves the app record by `(team_id, api_app_id)` and
  verifies the HMAC against **that record's** secret, failing closed on
  mismatch — the multi-secret trial alone proves only that *some*
  registered app signed the request, which must not let one app's secret
  admit events into another agent's DM spool.
- The admission owner for a DM conversation is that agent's own app —
  exactly one owner per DM, consistent with the single-admission-owner
  rule. DM events flow through the same durable admission spool with
  canonical key `(team_id, dm_channel_id, ts)`.
- Routing: a DM from an allowed human wakes the agent's singleton DM-bound
  session. Bot-authored DMs deliver nothing in v0 — delegation and results
  stay visible in company rooms; DMs never carry peer authority.
- Hydration, receipts, retries, and visible-ack semantics match rooms.

## Reliability and Loop Controls

- Ingress is deduplicated durably by canonical origin key, including across
  Slack redeliveries and adapter restarts. Receipt retention is 7 days
  (Discord parity) with a hard floor of 24 hours — terminal receipts are
  the dedup memory for late redeliveries, so retention below the Delayed
  Events horizon is rejected.
- Delivery workers hold an in-process single-flight claim per receipt; the
  sweep skips receipts claimed recently (stale-reclaim window), and
  receipt updates carry a generation counter so a lost race is detected,
  re-read, and merged rather than silently overwritten. All gc submissions
  on the company path use an HTTP client with an explicit timeout.
- The startup recovery barrier is company-scoped (legacy serves
  immediately); posting intents recover before pending ingress; the
  periodic sweep starts only after one successful pass.
- Outbound posts go through durable intents created before the provider
  POST, with CAS-guarded bounded attempts; `rate_limited` responses honor
  `Retry-After` within those attempts. Non-idempotent posts reconcile
  against channel history before any repost.
- Bot messages without a native target mention never ambient-wake agents;
  unknown bots, spoofed textual mentions, wrong rooms, unbound targets,
  replays, and ambiguous identities produce no delivery.
- Requests, results, and delivery failures remain visible in the human
  root's thread in the company room (`reply_broadcast` is never set, so
  they do not appear in the channel timeline outside the thread). DMs
  never substitute for room delivery of delegations or results.
- The switchboard receives events over HTTP (the existing public
  endpoint) or, when `SLACK_APP_TOKEN` is set and Socket Mode is enabled
  on its Slack app, over Socket Mode. Both transports feed the same
  admission path, so receipts, the startup barrier and origin dedup are
  identical; a retryable 503 leaves the socket envelope unacked so Slack
  redelivers it. Registered agent apps keep HTTP delivery: an app-level
  token covers only the app that owns it. See the README's Socket Mode
  section.

## Compatibility and Rollout

Company-room routing is additive and disabled when no directory is
imported. Legacy human ingress, alias dispatch, rig routing, room launch,
non-company rooms, and existing bindings retain their current behavior in
non-company rooms. For imported company rooms, the company path replaces
legacy fanout deterministically.

Required operator steps beyond pack install: enable Delayed Events on the
switchboard app; add `channels:read`, `groups:read` (Phase 1) and
`users:read` (Phase 2) to the switchboard manifest and reinstall; invite
the switchboard bot and member agent bots to each directory room;
optionally set `SLACK_SWITCHBOARD_BOT_USER_ID` so the switchboard can
classify its own posts (empty is safe in Phase 1 — self posts are bots
and bots wake nobody).

The pilot is a three-app proof in a scratch channel: one human ambient
request, exclusive `@riley` activation, one visible Ollie→Riley delegation
with metadata correlation, one visible result, restart recovery mid-flight,
a Slack redelivery absorbed by the receipt store, and a captured real
agent-app post event pinning the wire shape the mention extractor and
author classifier rely on — before creating the remaining identities.
Partially verified live (2026-07-17, workspace `T0ARJCFV8QL`, via
`chat.postMessage` + `conversations.history` readback): a real agent-app
post carries NO `subtype`, has `user`/`bot_id`/top-level
`app_id`/`bot_profile.app_id` (the classifier's corroboration chain),
Slack synthesizes `rich_text` mention elements for text-only posts, and
metadata round-trips on history reads with `include_all_metadata=true`.
Still pending the deployed events endpoint: metadata embedded in
`message.channels` event deliveries (load-bearing for receipt-based
reconciliation).

## Acceptance Gate

Automated tests must prove:

1. An unmentioned human message wakes exactly the configured ambient
   agents.
2. A human `@Riley` wakes Riley only, not ambient Ollie.
3. A trusted Ollie message with a native `@Riley` mention wakes Riley
   exactly once.
4. Textual mentions, unknown bots, webhook posts, self messages, wrong
   rooms, unbound targets, replays, ambiguous identities, and
   non-allowlisted subtypes (joins, topic changes) deliver nothing.
5. Riley's threaded result wakes only Ollie and correlates to Ollie's
   delegation record.
6. No unmentioned agent message produces ambient delivery or a loop.
7. A newly mentioned dormant agent receives the current request, verified
   human root, and a bounded untrusted excerpt without duplicate delivery.
8. An event admitted but undelivered at an adapter crash is delivered
   after restart: exactly once when the crash precedes gc submission;
   at-least-once with receipt-side suppression when the crash falls
   between submission and the delivery record (the documented duplicate
   window).
9. A Slack redelivery (`x-slack-retry-num` ≥ 1) of an admitted event
   changes nothing and returns 200.
10. A receipt-store write failure yields non-2xx without
    `x-slack-no-retry`, increments the write-failure counter, and a
    subsequent retry admits and delivers once.
11. A receipt whose room leaves the directory is parked, never terminally
    resolved, never legacy-delivered, and delivers after the room is
    restored.
12. DM phase: an allowed human DM wakes exactly the agent's DM-bound
    session; bot-authored DMs deliver nothing; DM replays are absorbed; an
    event claiming agent A's `api_app_id` signed with agent B's secret is
    rejected.

## Deferred

- Delegation chains longer than one hop.
- Dynamic discovery of agents or Slack identities.
- Cross-workspace rooms, Slack Connect, and shared channels.
- Socket Mode for registered agent apps (the switchboard has it; each
  agent app would need its own app-level token and connection).
- Slack token rotation automation (documented posture; disabled in pilot).
- Direct integration with the durable-request-ledger `/v0` API (tracked;
  blocked on those drafts landing in gascity).
- Credential delegation or transitive human approval.
