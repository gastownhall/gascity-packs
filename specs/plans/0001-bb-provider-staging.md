# Project-aware BB candidate qualification

Status: the exact GC integration candidate passed qualification in disposable
staging on October 7–8, 2026. Earlier-build results remain separately identified.
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


## Personal GC integration refresh

The generated contract now comes from personal GC branch
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


Current review conversations: Luna `thr_zjvncacxyr`, Haiku `thr_frr674vn6k`.
The final summary, native receipts, screenshots and exact binary are exported in
`bb-provider-project-picker/gc-update-oct7/`. The generated client is verified
against the serving supervisor; no raw terminal access exists in the BB bridge.
Optional top-level Codex model metadata can be absent after large output; model
qualification checks configured options and the exact native test artifact.
