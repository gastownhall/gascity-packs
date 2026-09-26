# GC 1.5 fix-gap analysis — 2026-09-26

The question: which of the nine GC runtime fixes in draft PR gastownhall/gascity#6481
(`fix/bb-runtime-v1.4.2`, `4f41f8285070`, on v1.4.2 `d4582166367a`) are still needed
on the Gas City 1.5 release candidate, and which are covered upstream. The user has chosen
1.5 as the target; the fixes that remain are carried on a 1.5-based branch to contribute after
the 1.5 release.

## Tested revisions

| Ref | Commit |
| --- | --- |
| `origin/release/v1.5.0` (the 1.5 RC branch; no `v1.5*` tags exist yet) | `750ee90205f0` |
| `origin/main` | `da84dbfedca3` |
| Hillsboro forward-port `hillsboro/1.5-dev-bb` in `/home/ubuntu/src/gascity-1.5-dev-bb` (read only) | `8ab11cc90a71`, on release/v1.5.0 `26172ff4b` |
| Contribution branch `fix/claude-runtime-v1.5.0` (pushed to gastownhall/gascity; no PR until 1.5 ships) | `002016a8679a`, on release/v1.5.0 `750ee90205f0` |

Clone: `~/code/gastownhall/gascity` (from github.com/gastownhall/gascity). Builds, both
`make build` with Go auto-toolchain 1.26.6:

- Unmodified RC: `~/code/gastownhall/gascity/bin/rc/gc` → `1.5.0-rc+750ee9020`.
- RC plus the fixes below: `~/code/gastownhall/gascity/bin/gc` → `1.5.0-rc+002016a86`.

## Method

Each fix's own regression tests were the oracle. The test files (and `testdata/`
fixtures) from the eight Hillsboro forward-port commits plus the tests from `0001` were
applied, without any production-code change, to a scratch worktree of unmodified
`release/v1.5.0`, and the named tests were run with `go test -count=1 -run …`. A test that
fails there and passes with the fix means the fix is still needed. The same oracle was then
repeated on unmodified `origin/main` (branch trial-rebased onto main, then every non-test file
restored to main).

Two adaptations were needed because the fixes change internal APIs, not behavior under test:

- `0004`: the test edits to `session_lifecycle_parallel{,_phase2}_test.go`,
  `session_reconcile_test.go` and `session_reconciler_fork_launch_test.go` only follow the
  new `staleResumeKeyProbe(searchPaths, …)` signature; they were reverted and only the new
  `session_resume_identity_test.go` was run.
- `0001`: its tests call a 1.4.2 signature and `ErrUnrecognizedWorkspaceTrust`, neither of
  which exists on 1.5. Its eight trust-menu fixtures were instead run through 1.5's
  `workspaceTrustConfirmKeys` (a throwaway oracle test, not committed).

## Results

| # | Fix | release/v1.5.0 | main | Evidence (unpatched → failure) |
| --- | --- | --- | --- | --- |
| 0001 | Claude workspace-trust selection | **covered upstream** | covered upstream | #6547 (release backport `58dfd3c9d`/#6594, main `e94c36720`) replaces blind confirm with a closed loop. See below. |
| 0002 | Claude API failures as provider errors | **still needed** | still needed | `TestClaudeAPIErrorAfterPartialResponse` (`event=<nil>`), `TestClaudeAPIErrorRequiresExplicitFlag/true`, worker `TestClaudeAPIErrorProjectsSystemFailure`. main's #6583 (pending-create rows on terminal provider errors) does not classify transcript entries. |
| 0003 | Preserve conversation on intentional suspend | **still needed** | still needed | `TestSuspendPreservesConversationAcrossExitClassification` ("intentional suspend classified as 3/4"), `TestSuspendDoesNotStopWhenExitTrackingCannotBeSaved`. |
| 0004 | Preserve allocated session identity across launch preparation | **still needed** | still needed | `TestBuildPreparedStartPreservesAllocatedKeyUntilFirstTranscript` ("preparation 0 rotated unlaunched key"), `TestBuildPreparedStartResumesExactObservedTranscript` ("existing observed transcript key replaced"). |
| 0005 | tmux: bind approval responses to visible menu choices | **still needed** | still needed | 9 of 10 tests fail. Safety-relevant: `TestRespondClaude270DeniesWithoutChangingPermissionMode` — a denial on Claude 2.1.270 sends `3` (switch to auto mode) instead of `4` (No); `TestRespondApprovalNeverEscalatesPermissions` — unsafe actions succeed; `TestPendingCurrentClaudeBashApproval` — current approval not detected. |
| 0006 | tmux: cancel approvals before confirming idle | **still needed** | still needed | All 6 `claude_interrupt_test.go` tests fail: interrupt sends `C-c` instead of `Escape`, approval/menu accepted as idle, copy mode not exited. |
| 0007 | Claude transcripts in underscore-normalized project dirs | **still needed** | still needed | `TestFindSessionFileByIDClaudeUnderscoreWorkspace` (keyed transcript `""`), `TestHasKeyedTranscriptClaudeUnderscoreWorkspace`. |
| 0008 | Tool-use interruption marker ends the turn | **still needed** | still needed | `TestToolUseInterruptActivity/[Request_interrupted_by_user_for_tool_use]/*` → activity `in-turn`, want idle. |
| 0009 | Marker only as a standalone native message | **still needed** (refines 0008) | still needed | Same test file; ships with 0008. |

No fix is obsolete: every touched code path still exists on 1.5 and main.

### 0001 detail

1.5's `acceptWorkspaceTrustDialog` locates the cursor row and the trust row, sends movement
keys alone, re-reads the pane, and sends Enter only after two consecutive frames show the
cursor on the trust row (at most three moves); otherwise it returns
`ErrWorkspaceTrustUnconfirmed`. 0001's fixtures through 1.5's key derivation:

| Fixture | 1.5 keys | 0001 expectation |
| --- | --- | --- |
| cursor on "No, exit" | Down (then Enter only after the loop sees the trust row) | Down, Enter |
| cursor on trust row | Enter | Enter |
| legacy numbered, cursor on "2. No, exit" | Up (then Enter) | Up, Enter |
| unknown option ("Yes, trust all folders") | none | blocked |
| unselected (no cursor) | none | blocked |
| extra "Trust parent folder" row | Down (then Enter) | blocked |
| truncated (no footer) | Down (then Enter) | blocked |
| dialog in scrollback under a live prompt | Down (then Enter) | blocked |

The defect BB hit — Claude exiting in a fresh workspace because the default "No, exit" was
confirmed — is fixed by #6547, and 1.5's closed loop is also robust to dropped keys, which 0001
was not. Remaining differences are stricter-parsing hardening, not required behavior: 1.5 only
warns (`adapter.go`, post-readiness pass) and continues startup when the trust row is never
reached, where 0001 blocked startup; and 1.5 accepts the last three fixtures above. The
Hillsboro forward-port already dropped 0001. Not carried on the new branch; revisit only if a
live 1.5 run shows a trust failure.

## Contribution branch

`fix/claude-runtime-v1.5.0` = `release/v1.5.0` (`750ee9020`) + the eight Hillsboro
forward-port commits (0002–0009), cherry-picked with `-x`, no conflicts:

```
65c7e18af Classify explicit Claude API failures as provider errors
15d6e5af9 Preserve provider conversation when intentionally suspending sessions
52cb696e1 Preserve allocated session identity across launch preparation
0d3a1c931 fix(tmux): bind Claude approval responses to visible menu choices
c4146cc10 fix(tmux): cancel Claude approvals before confirming idle
b0ed66934 Find Claude transcripts in underscore-normalized project directories
7aa69542e Recognize Claude tool-use interruption as idle
002016a86 Limit tool interruption marker to standalone native message
```

`git range-diff` against the original #6481 commits shows only adaptations to code 1.5
restructured, with unchanged intent: `0003` restores the wake stamp around 1.5's reshaped
suspend-stop error path; `0004` applies the `StartedConfigHash` guard to the key-clearing
condition instead of the probe condition and also updates the probe call in
`cmd/gc/session_reconcile.go`; `0006` passes the provider family into 1.5's
`snapshotPaneIdleWithPrefix` as a parameter. Commit messages do not mention BB.

Verification on the branch:

- `make build` and `go vet` on the touched packages: pass.
- `go test -count=1 ./internal/sessionlog/... ./internal/session/... ./internal/runtime/... ./internal/worker/...`: all pass, including every regression test above.
- `go test -count=1 ./cmd/gc/` (270 s): 12 failures, all environmental. The identical 12
  fail on unmodified `release/v1.5.0` in the same shell. Causes: the shell's `umask 0077`
  (`TestNormalizeCanonicalBdScopeFilesPreservesProviderOwnedScopeFiles`, `mode = 600, want 640`,
  and the two `TestDoInitFromDir…` tests) and the sandbox HTTPS proxy breaking `gc init`'s
  `git clone` of gascity-packs (the nine `…Init…` tests). With `umask 022` and a direct
  connection, all 12 pass on the fix branch. The rest of the suite passed.
- Trial rebase onto `origin/main` `da84dbfed`: all eight apply without conflicts; vet and the
  same internal package suites pass there. The branch should rebase cleanly once 1.5 ships.

Not yet done: the repository's full pre-push gate (`make test-fast-parallel`, lint), and any
live run. Unit tests do not establish live BB acceptance; the 40-case matrix must be re-run
against a build of this branch in scratch state.

## Hillsboro production note

On 2026-09-24 21:33Z `bb-gascity-gc.service` was switched from
`releases/1.4.2-bb-runtime.4f41f8285070/gc` to `releases/1.5.0-dev-bb.8ab11cc90/gc` (the
forward-port above, built from `/home/ubuntu/src/gascity-1.5-dev-bb`); the prior unit is kept
as `bb-gascity-gc.service.before-1.5.0-dev-bb-20260924T213332Z`. On 2026-09-25 `bb.service`
gained `BB_CLAUDE_CODE_EXECUTABLE=/home/ubuntu/.local/share/gascity-tools/claude-bb-sdk-shim-manifold410.py`.
No retained 40-case ledger or production-verifier run for `8ab11cc90` was found; that build is
unqualified until one exists. Its fix content equals the new branch except for the older
`release/v1.5.0` base (32 commits behind `750ee9020`).

## Additional 1.5 regression: fresh Codex sessions drained for config drift

Found after the analysis above, when CI's Codex live jobs failed on both the RC and
the candidate with "GC startup did not become ready; no BB prompt was sent" (run
36219869688; the Codex credential preflight passed). A local reproduction showed GC
draining its own new session about one second after start:

```
config-drift s-gc-5: ... drifted fields: CopyFiles
  [+] ../workspaces/global/.codex/hooks.json  stored=(absent)  current=a468b4ee (probed)
Draining session 's-gc-5': config-drift
```

Cause: #3919 (`2c99b57b8`, in `release/v1.5.0`, not in v1.4.2) made the
pre-fingerprint overlay staging in `cmd/gc/build_desired_state.go` skip every
mergeable hook file, assuming `hooks.Install` writes them. `hooks.Install` only runs
for providers in `install_agent_hooks`, so for a Codex agent without it,
`.codex/hooks.json` is absent when `stageHookFiles` fingerprints CopyFiles, then
session-start staging writes it and the next reconcile drains the session. Any
first start of such an agent in a workspace without the file triggers it; work_dir
location, custom commands and API creation do not matter. A GC-only reproduction
(`gc session new`, plain `builtin:codex`) drained on the RC and stayed active on
1.4.2 and on the fixed build. No upstream issue or fix was found on `origin/main`
`2d7d33954`.

Fix `876b06123` ("fix(hooks): stage overlay-only codex hooks before fingerprinting")
is now on `fix/claude-runtime-v1.5.0`. It still stages the fingerprinted hook files
whose provider is not in `install_agent_hooks`, keeping #3919's protection for
files `hooks.Install` owns. Its regression test
`TestResolveTemplatePrepared_CodexOverlayHookNoFirstStartDrift` fails without the
fix with the same `stored=(absent)` diagnostic and passes with it. Full
`go test ./cmd/gc/` passes (umask 022, direct network), as do
`internal/runtime/...` and `internal/hooks/...`; `go vet` is clean.
