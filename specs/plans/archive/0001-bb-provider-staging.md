# Project-aware BB candidate qualification

Status: complete; foundation candidate qualified in disposable staging. Chris's merge/promotion approval remains separate.

## Current integration candidate

GC `077c53b553f0d92fde2c6b425c9a197ce473a791` / `1.6.0-dev-jarvis.8-bb-integration.10` is verified in disposable VM140.
SHA-256: `151afd75b204d969caebd51260a6861d02c52ac952d2b1b372763c4f95d2ab0c`. The exact generated-client provenance pins this commit.
BB remains `6e5c1c6fd29b507b812df6d07017904e2a315669`, based on
main `81256f5d42c9225398650fb3e5e80644d49c7e52`, with SDK runtime 0.6.28.

The first full gate caught a missing runtime-test manifest entry for the new
fast-turn regression. The manifest and shard counts were corrected before the
final gate; the failing log remains in the evidence.

An integration run also hit the unchanged upstream shutdown test’s 100 ms
forced-stop budget under concurrent load. A focused repeated run and the full
integration retry with two test slots passed on unchanged source. The initial
failure remains recorded; this is not a claim that the timing-sensitive test was
repaired.

The first .10 staging cutover failed because BB’s local API port was already
in use. Runtime rollback preserved conversation state. The service ports are
now excluded from automatic client-port allocation; cutover waits for both BB
ports and verifies the connected execution host plus thread API. The original
socket owner was not established. Failed-cutover evidence is retained.

The staging housekeeping role also has its own working directory. Its four GC
hooks were byte-identical to the reviewed city hooks, but native resume required
consent for that path. Provisioning trusts only those exact hashes, preserves all
other settings, and verifies the retained conversation after resume.

The first rendered Stop check caught a BB bridge ownership leak: GC stopped
the command, but a still-running shared bridge retained its local thread lease,
blocking the next bridge from resuming. A regression reproduces that handoff
without closing the first bridge. Both Stop intents now release the stopped
thread; interruption waits for cleanup before its response. Other conversations
keep their ownership, and uncertain delivery still requires explicit recovery.
The final provider checks and full rendered matrix include this correction.

The final artifact passes all 235 native Bazel targets, seven selected integration
targets, generated-client/typecheck/build checks, 85 provider tests plus two
client guards, 199 pack checks without skips, and 29 browser-driver guards.
Live checks pass Claude foreground and explicit-background Stop, Codex command Stop, absence of delayed writes,
explicitly detached service preservation and another conversation surviving for both providers,
repeated old Stop while a new turn runs, crash recovery retaining native identity, sleeping-conversation follow-up without replay, and migration of an actual embedded
Codex conversation with exact native identity, ordered history and remembered
context. Rendered BB checks cover project-filtered agents and fox icon, both
providers' five-turn conversations/tools (including sleeping-context recall) and Stop. Native approval allow/deny and a follow-up after denial,
lost-submit-reply recovery without replay, release, durable closure, and protected
conversation continuity pass through the generated supervisor client.

Claude uses the pinned 2.1.292 binary, SHA-256
`a967e7b1d8b4e47ee421d5433027880347952b0c0857abf880e2c942a4ec93b3`.
Its GC adapter retains native Bash task handles and requires matching native
exit notifications. It preserves explicit detachment and old-turn fences.
Unknown native versions/tools, unresolved starts, attached human clients and
ambiguous identical live commands fail visibly; they never become false Stop
success. The initial .8 live run exposed surviving Claude background work;
foreground-handle, multi-task navigation and denial-follow-up failures are retained
in the evidence. An ordinary denial permits a follow-up; explicit Stop intent is
persisted before native mutation and stays uncertain until command exit is confirmed.

Codex uses the pinned custom 0.156.1 bundle, SHA-256
`d4b29ce977ae553da6707bdb702e135a4e91d321914438ac52d6eb5c7a75f57a`,
with its matching helper. Its source and build instructions are in GC's
`contrib/codex-owned-stop/`. Both live models use subscription authentication:
Luna and Haiku at medium effort. Temporary build swap and protocol observers
have been removed. Stable installations remain unchanged.

The .9 live run exposed a native-acceptance retry bug: terminal busy had ceased
to prevent another submit, allowing Escape to abort work before acceptance was
recorded. A failing regression reproduces the extra keys. Owned Codex now uses
bracketed paste and Enter; busy suppresses retries while exact native acceptance
still determines success. Lost control after a submit remains unconfirmed. A subsequent load probe
showed an exact receipt arriving after eleven seconds, beyond the old eight-second
paste-recovery budget. Native acceptance now has its own sixty-second bounded
wait, covered by a failing-then-passing delayed-receipt regression. The failed
probe later returned READY exactly once, without replay; its trace is retained.

Fast Codex turns, including the first follow-up after native resume, now use
native acceptance of the exact message to acknowledge delivery. The earlier .7
rendered run completed the native turn but failed its terminal-busy check; its
failed receipt was preserved and never replayed. The final candidate passes the
same rendered sleep/resume flow.

Committed conversations now retain their identity after startup failure. The
native adapter reclaims confirmed stale Unix sockets without replacing live
listeners and handles terminal hangup through graceful cancellation.
The staged city and rig Codex roles explicitly declare GC-managed hooks before
fingerprinting. The first rendered run exposed a missing rig declaration; its
drift-drained disposable thread was archived without replay, the declaration
was repaired, and the rendered flow rerun. The native adapter finalizes canonical
reviewed hooks before startup and carries
explicit resume approval/sandbox choices through the native API, verifying the
response before accepting the session. Custom profile, extra-root, auto-review,
and permission-config overrides on remote resume fail explicitly; supported
`--sandbox` and `--ask-for-approval` flags remain available. No user trust or
permission defaults are silently replaced.

[Open the review VM](https://csells-mac-mini--51995.getbb.app), select
**GC City — globals** or **GC Sample — rig + globals**, then the fox and an agent.
The Mac mini is a web relay only. The sample rig is still qualification scaffolding,
not the Gotham application repositories. Jarvis voice, Gotham composition,
Crucible and binding arbitrary existing GC sessions are separate future work.

Operational limits from final log review: one 900-second bead-archive export
expired during qualification; the next scheduled run exported both scopes and
committed valid JSONL without intervention. Resource contention is plausible,
not proven. Track recurrence before promotion. GC's current API suspend endpoint
stops the native runtime without the persistent operator hold used by CLI suspend;
three completed review fixtures resumed under their sleep-off policy and retained
their native identities. They remain idle review conversations. Persistent API
suspension is not qualified, is not exposed by this BB integration, and must be
addressed before relying on it for orchestration resource control. BB Stop,
release, durable close and sleeping-context follow-up have independent passing
checks. The warning review and registry retain these follow-ups.

This qualifies this Linux staging combination. Earlier installer/reboot evidence
belongs to earlier builds; this run did not reboot the shared VM or qualify macOS.
The native Rust suite had one timeout that passed on isolated retry and two skips;
those limits remain recorded. Branch publication is not approval to merge or
promote. Chris must approve this exact staged candidate first.

Retained evidence: `/Users/csells/.bb/thread-storage/bb-provider-project-picker/stop-contract-oct8/final-candidate10/`. The exact final provider snapshot is
`provider-lease-fix/verified-provider.tar.gz` there; it supersedes the initial
provider snapshot without changing GC's binary.
Earlier failures below remain historical evidence and do not describe this candidate.


## Earlier foundation qualification

The minimal city imports core and BB, plus required bd/Dolt storage packs. It does not depend on Jarvis, Gotham,
the GC engineering pack, or Crucible. Candidate execution, browsers, workspaces,
GC and BB run in disposable Badger VM140. The Mac forwards web traffic only.

Verified so far: rendered project filtering and city/agent labels; Luna/Haiku
multi-turn conversations, retained-context tool artifacts, native identity and
history across crashes/reboot; allow/deny with both providers; withdrawn, timed-out and
already-pending approvals; interruption and detach for both providers; lost HTTP
submit responses with exact prompt proof and explicit receipt recovery; actual
installer upgrade, failed-registration rollback, and manual rollback preserving
43 receipts. Plugin tests: 78 plus two generated-client guards and typecheck.

The exact Claude pasted-content envelope is recognized without trimming the
payload or accepting mismatched IDs, appended text or a different provider.
Uncertain delivery remains visible and cannot be silently retried.

Final GC repairs additionally cover native Codex stop events tied to the correct
session, the current Codex on-request approval policy, refusing an unsafe fresh
launch fallback, and recognizing/responding to the native command approval menu.
The stale process-environment test now waits until its child is ready before
measuring the intended exec race; its old failure also reproduced on clean base.
The final candidate passes native Codex allow/deny, interruption for both providers,
12,176 distinct CLI tests, affected core/API/runtime suites, manifest guard, vet
and the live generated contract check. One initial CLI shard exceeded the Unix
socket fixture’s path limit with a long TMPDIR; the identical shard passed using
/var/tmp. The original failure is preserved alongside the successful retry.

Four fresh city/rig review conversations verify the exact receipt target and
actual native model. Each passes two turns and VM-local tool artifacts. BB restart
and full VM reboot preserve every native identity and ordered history; both rig
agents pass retained-context writes after BB restart and all four pass after
VM reboot. Historical city-Haiku evidence actually selected Codex and is excluded.

VM140 now has 6 vCPUs, 14 GiB RAM and 80 GiB disk with host headroom preserved;
temporary build swap is removed. GC candidate 1.6.0-dev-jarvis.7-bb-qualified
SHA-256: c6d972793b665497a7715c87d7c718b8d2539c024476243dd7dc77704f5dca1f.
All source/evidence and the exact binary are retained outside the disposable VM.

Compacted/rotated history without an authoritative continuity proof is rejected.
Codex command approvals are covered; other interactive Codex menu types are not
claimed. Timeout acceptance injects BB's interaction-timeout response while GC
has a real pending approval; it does not pretend to measure BB's wall-clock timer.

## October 7 reported-turn repairs

The earlier parser-repair VM build was `1.6.0-dev-jarvis.7-bb-history`. GC now scans beyond the
64 KiB metadata tail for Codex lifecycle markers and retains Claude parallel tool
result attachments in the active history. Both changes have failing regressions,
captured transcript replay and passing affected sessionlog/worker/API suites and
vet. Fresh Luna and Haiku rendered rig conversations pass four completed turns,
including large output and native GC/BB CLI checks. Haiku also exercises parallel
calls with both results present through the generated supervisor API. The live
OpenAPI contract is unchanged and verified.

The earlier full CLI, installer, reboot and approval matrix belongs to the
previous qualified binary; those broad gates were not repeated for this parser
repair. The external manifest records exact final hashes and separate evidence.
The original user turn was recovered after confirming native completion, without
resending any prompt or resetting its session. Its historical BB error remains.
VM-only CLI entrypoints and required storage pack imports were repaired as well.
Stable services are unchanged; Chris must approve this final staging candidate.


## Earlier .2 personal GC integration refresh

The earlier generated contract came from personal GC branch
`csells/gascity:fix/bb-supervisor-continuity`, commit
`992a8dd485239b74214a0c3befe80fb5bec25669`. Build
`1.6.0-dev-jarvis.8-bb-integration.2` has SHA256
`4515da0f4b66a8b0ee301cca797cbd53b5a698abac7cd21159a1c612c4d01957`.
It combines pinned upstream main and pending-interaction/API PRs with our BB
continuity changes. Qualification found and repaired API-create command drift,
repeated live work lookups, manual-session recreation after close, and a native
pre-push hook that could skip large diffs.

Exact-source native checks pass 234/234 targets and five selected integration
targets. Plugin schema regeneration, typecheck, 78 tests, two contract guards
and build pass. The staged live schema matches the generated client. BB remains
rebased on main `81256f5d42`, candidate `6e5c1c6fd`, SDK runtime 0.6.28.
Six picker cases and four rendered turns each for Luna/Haiku pass. Both providers
pass native allow/deny, lost-submit-response recovery without replay, release
and interruption. All eight closed fixtures stay closed across two reconciliation
windows, as do ten previously recreated task fixtures. The original repaired user
conversation retains native identity and history without prompt replay.

VM140 has 6 vCPUs, 14 GiB RAM and 120 GiB disk. Temporary build swap is removed.
All execution stays inside the disposable VM; the Mac is only a web relay.
The earlier installer/reboot matrix is historical evidence for its own build.
BB fork CI is queued without a runner, not passing. No merge or stable promotion
is approved.


Earlier .2 review conversations: Luna `thr_zjvncacxyr`, Haiku `thr_frr674vn6k`.
The final summary, native receipts, screenshots and exact binary are exported in
`bb-provider-project-picker/gc-update-oct7/`. The generated client is verified
against the serving supervisor; no raw terminal access exists in the BB bridge.
Optional top-level Codex model metadata can be absent after large output; model
qualification checks configured options and the exact native test artifact.


## PR 7076 port — October 8: staging has a cancellation blocker

GC `303790c4890fa481cfc016af99223c618e4546f5`, build `1.6.0-dev-jarvis.8-bb-integration.3`, serves only disposable VM140.
SHA256: `3d6c84adfb5faf839335c7f199c0cb0aea197445d64e8887817019ccf4209cc2`.
It ports the missing `creating`-state wake exemption from PR 7076
`41fec8ba6442fe28d252aacfbeb188a15c98fd5f`, preserves `start-pending` refusal,
and adds API/CLI and evicted-close regressions. Existing readiness and close-event
fixes are retained. Shared rig-template edit scope and concurrent event ordering
are clarified. The wake regression fails before the fix; a negative control
confirms that losing a queued close claim drops its required event.

Native pre-commit passes, all 234 native targets pass, and six selected integration
targets pass: CLI, API, tmux, session, dashport and beads. These six are not the
entire upstream integration suite. Generated schema/client code is unchanged;
the BB pack's provenance pins this build. All 78 plugin tests, two contract guards,
typecheck and build pass, as does equality with the serving supervisor schema.

Live checks pass six picker cases and four rendered rig turns each for Luna and
Haiku at medium effort. Both pass approval allow/deny, lost-submit reply recovery
without replay and release. Claude also passes interruption with no delayed file.
Codex reports the turn interrupted but its shell command continues and writes the
file. A second reproduction waits for a command-start marker before Stop and
fails the same assertion. This is **not** a fully qualified candidate.

Codex 0.156.1 and latest stable 0.161.0 deliberately retain Unified Exec processes
across turn interruption. See [upstream issue 42717](https://github.com/openai/codex/issues/42717)
and the [pinned implementation](https://github.com/openai/codex/blob/rust-v0.156.1/codex-rs/core/src/unified_exec/process_manager.rs#L598).
The observed Stop acknowledgment is not proof of command exit. Earlier isolated
passing interruption samples do not establish that stronger guarantee. The
no-delayed-artifact acceptance criterion remains unmet; it has not been weakened.
Chris's choice of turn-only interruption versus command termination remains open.
Do not add client-side process killing or replace generated supervisor APIs.

All nine disposable native fixtures, including the failed reproductions, close
and remain terminal across 90 seconds. The two original user threads and both
previous .2 review conversations retain their native identities and ordered
histories; the preexisting missing session remains missing and unrebound.
Original-thread resume requires no inference or replay. Temporary 8 GiB build
swap is removed; readiness, binary/helper hashes and the closed profiler are
verified. An early empty-picker screenshot showed a generic provider glyph;
rechecking with an explicit provider-control wait passes all six cases. Both
initial and settled screenshots are retained; no BB source change was made.

Review conversations: Luna `thr_ehbqaf4iaf`, Haiku `thr_fvqgtpucbp`.
[Open staging](https://csells-mac-mini--51995.getbb.app). The Mac relays traffic;
all execution remains in VM140. Exact binary, native logs, screenshots and failed
cancellation evidence are retained in `bb-provider-project-picker/pr7076-port-oct8/`.
BB remains `6e5c1c6fd`, rebased on main `81256f5d42`, SDK 0.6.28. Codex remains
0.156.1; merely updating it would retain the same documented cancellation policy.
Earlier installer and whole-VM-reboot results belong to their earlier builds.
Development-branch publication does not approve any upstream merge, release or
stable promotion. The cancellation blocker must be resolved before qualification.
