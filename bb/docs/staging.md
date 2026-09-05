# Staging the BB integration

## Stage 1: this branch, released GC 1.4 and current BB

Keep the provider in `gascity-packs/bb`, independently installable. Use BB's
provider registration, workspace model catalog, host-side bridge, thread
identity, normalized deltas, interaction UI, and lifecycle contracts. Use
Gas City's supervisor discovery, expanded configuration, durable sessions,
request-result events, and structured transcripts. No GC or BB fork is
required by the adapter.

Agent IDs are opaque `gc1_` encodings of a versioned tuple:
`{ connection, city, agent }`. The agent field is GC's exact qualified name,
including its rig and pack binding. Display names are presentation only.
GC session IDs are separate from agent identities and from BB thread IDs.

Mappings are local to the selected BB execution host. Explicit project IDs
win at execution; real workspace paths provide the discovery context that BB
currently supplies. A project maps to exactly one connection/city/rig on a
host. Projectless discovery spans all running cities; project discovery spans
only the mapped city, admitting its globals and matching rig.

This stage deliberately leaves BB's model field and picker in place. An
agent ID uses that existing transport field without pretending the backing
LLM model can be changed. Scope is checked again on session creation, so
stale catalogs do not authorize a wrong-rig launch.

## Stage 2: smallest useful BB PR

The next BB change should be generic provider infrastructure. Keep all GC
discovery and project-to-rig policy in this pack.

1. **Pass project context to provider catalog discovery.** Add optional
   `projectId` to the app/server/host/bridge model-list request, preserving
   `cwd` for existing providers. Send the selected project before workspace
   allocation. Include project, host, provider, and effective workspace in
   cache identity. Refresh on project/host/provider changes and discard late
   responses belonging to a previous selection.
2. **Let providers describe the selection.** Optional provider metadata can
   supply a label such as `Agent` and optional group/scope descriptions.
   Existing providers default to `Model`. Retain the current model ID
   transport in this PR; no new thread storage column is needed just to
   carry an opaque agent ID.
3. **Make an invalidated selection explicit.** For catalogs that opt into
   exact selection, clear an unavailable selection and require a new choice
   instead of silently replacing it with the default row. Support loading,
   empty, unavailable, and error states plus an explicit refresh path.

With that contract, New Thread becomes: choose host/provider and optional
project, fetch that context's catalog, choose an agent, then create the
thread. This pack would pass the supplied project directly to `discover`
and advertise `Agent`; the HTTP adapter and session mapping stay intact.

Tests for that BB PR should cover no project → all global agents, project A
→ A's city globals and rig, switching to project B while A's response is in
flight, duplicate display names, disconnected hosts, removed agents, empty
catalogs, and existing model providers with no new metadata.

Workspace ownership is a separate extension. Allowing a provider to adopt an
existing checkout or supply its own workspace should be explicit before
showing GC edits in BB's file/diff views. A project ID by itself cannot make
two worktrees identical.

## Stage 3: richer GC integration

Add canonical/dormant named-session discovery only when GC exposes a catalog
that expresses launchable templates, named targets, scope, availability,
and runtime capabilities without duplicating GC's configuration resolver.
Give new conversation and attach-to-existing-session distinct semantics;
arbitrarily sharing a canonical agent conversation is not a safe default.

Server-side idempotency for create/submit would allow automatic reconciliation
after a lost response. Until then, the durable journal blocks uncertain
delivery instead of claiming exactly-once execution. Full interrupted-turn
replay also needs an explicit reconciliation contract with BB's persisted
history. Expand runtime interactions and workspace adoption with their own
compatibility tests, rather than treating all runtime providers as equivalent.

## Verification and release gates

Automated verification for this branch uses:

- GC release **v1.4.0**, commit
  `a7297c511d637a3609947386f3389d76ddb2f23b`.
- Published `@get-bb/plugin-sdk` **0.4.47**, plus source review of BB main at
  `38956e29fcba9285ee3d7575c0f1e5caa188ada9`.
- HTTP/SSE fixtures checked against that GC release, BB's published bridge
  conformance harness, TypeScript checks, and actual GC CLI pack loading.

Before promoting the pack to the registry, run a live BB installation with
GC 1.4.0 and a configured model runtime. Verify at least one global and one
rig agent, a multi-step tool turn, a real approval, a second prompt,
completed-thread restart, interrupt, release without killing the agent, and
the configured workspace mismatch policy. Check the actual New Thread and
existing-workspace picker behavior and document the BB version used. These
live UI/inference checks have not been performed by the automated fixtures.

Then commit the tested pack content and use this repository's normal
`gc pack release`/registry publishing process to stamp a content-addressed
release. This branch intentionally adds no speculative registry entry.

## Primary contract references

- [GC 1.4 expanded configuration](https://github.com/gastownhall/gascity/blob/v1.4.0/internal/api/huma_handlers_config.go)
  supplies binding-qualified agent names, rig directories, and suspension.
- [GC structured transcript types](https://github.com/gastownhall/gascity/blob/v1.4.0/internal/api/session_structured_types.go)
  and [session streaming](https://github.com/gastownhall/gascity/blob/v1.4.0/internal/api/handler_session_stream.go)
  define the normalized messages, cursor, pending interactions, and tail state.
- [GC API source](https://github.com/gastownhall/gascity/tree/v1.4.0/internal/api)
  defines session create/submit and request-result events used by the client.
- [BB plugin SDK](https://github.com/get-bb/bb/tree/38956e29fcba9285ee3d7575c0f1e5caa188ada9/packages/plugin-sdk)
  provides registration, bridge protocol, and the public testing harness.
- [BB catalog memoization](https://github.com/get-bb/bb/blob/38956e29fcba9285ee3d7575c0f1e5caa188ada9/apps/server/src/lifecycle-dedupers.ts)
  explains why a browser reload alone is not a catalog invalidation mechanism.
- Existing [Slack channel](../../slack-channel) and
  [runtime Cloudflare](../../runtime-cloudflare) packs inform the adapter,
  command, doctor, explicit setup, and independent-test layout.
