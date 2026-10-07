# Project-aware BB candidate qualification

Status: bounded foundation qualification passed, October 7, 2026. Ready for
staging review; not approved for merge or promotion. The exact manifest and retained evidence are in Chris's external
`bb-provider-project-picker` run directory; they are deliberately outside the VM.

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

The current VM build is `1.6.0-dev-jarvis.7-bb-history`. GC now scans beyond the
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
