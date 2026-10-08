# Project-aware BB candidate qualification

Status: the PR7076 candidate is staged; October 8 live qualification exposes a
native Codex command-cancellation blocker. Earlier-build results are separate.
No candidate is approved for merge or promotion. The exact manifest and retained evidence are in Chris's external
`bb-provider-project-picker` run directory; they are deliberately outside the VM.

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
