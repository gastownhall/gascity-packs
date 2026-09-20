# BB production readiness

## Objective

Finish the remaining provider work and Hillsboro installation using BB 0.43.3
(SDK 0.4.104), GC 1.4.2 plus verified required runtime corrections, and the
available Claude and Kimi routes through Manifold. This advances the original
[assessment](../research/bb-production-readiness-2026-09-06.md), which targeted
BB 0.42.1 and GC 1.4.1. Retain historical compatibility results with their exact
versions. Native BB frontend changes and the listed richer v1 exclusions remain
outside this pack change.

The user's current Hillsboro goal can use Kimi through Claude's Anthropic
adapter; this does not certify GC's native Kimi CLI, full Codex acceptance,
stock-GC CI, or the separate macOS desktop/publication gates. Preserve those
outstanding requirements rather than marking them passed. Current evidence:
[Hillsboro qualification](../research/bb-hillsboro-verification-2026-09-19.md).

## Work and verification

- [x] Correct repeated approval handling, busy-turn steering errors, and stale workspace discovery, with regression tests.
- [x] Enforce durable ownership and safely reconcile uncertain creation/submission and crashed operations; test active/recovery races without blind resubmission.
- [x] Add a host/project/agent/workspace launcher that keeps exact selections, refreshes and reports errors, validates at execution, and uses BB's native styling.
- [x] Enforce matching workspaces for project work; support personal global conversations in GC's own directory and explicit conversation-only project work.
- [x] Stage and validate upgrades before activation, retain previous installations, and exercise rollback failures while preserving config and journals.
- [x] Improve diagnostics and update user setup/recovery docs and compatibility declarations.
- [x] Verify actual BB/GC installation and UI with isolated Hillsboro state on Manifold Kimi through Claude CLI 2.1.270: all 40 cases pass, including global/rig agents, two turns, tools, approval/denial/repetition, busy follow-up, interrupt/release, restart/resume, failures/recovery, and mismatched workspaces. Exact provider `b17e84154ec3…` and patched GC `4f41f8285070…`.
- [x] Extend build, fixture and CLI CI to the release matrix.
- [x] Pass retained development Claude global/rig/underscore and Codex global/rig three-turn/tool/resume checks, with full forwarded-prompt and stable-identity evidence.
- [ ] Pass actual Claude and Codex two-turn/tool acceptance in CI on GC 1.4.0 and 1.4.1; build/fixture success alone is insufficient.
- [x] Commit/push the implementation for review: provider commit `0a9d6f0`, draft PR #455, and exact GC candidate `4f41f8285070`, draft PR #6481.
- [x] Deploy the exact qualified artifacts to Hillsboro and pass read-only production verification of all 121 pins, service identities, installed provider, six role prompts, connections, bindings, and global/mapped-rig catalogs; preserve original state and submit no production test inference.
- [ ] Complete the native Claude/Codex full matrices and separate macOS qualification.
- [ ] Publish a versioned pack through the repository's release workflow only after release gates pass.

## Preservation and evidence

All running test services, cities, threads, installations, logs and generated outputs belong to scratch roots. Existing user BB/GC state is not a test target. Preserve uncertainty on ambiguous remote outcomes. Record actual verification outcomes below; fixture success does not substitute for live UI/model execution.

Initial implementation base: `b8b255256d7fc218e3a6854d5b2069c515c5c17f`.
Initial working tree: only the untracked assessment under `specs/research/`.

## Full end-to-end gate

The full-product runner now declares 40 required cases and drives the released
BB UI, including personal and mapped-project conversations, all six reasoning
choices, fresh trust, manual permissions, visible errors, and process/transport
faults. The earlier conversation smoke runner remains a narrower gate. The
complete revised matrix passed all 40 cases on Hillsboro's Manifold Kimi route
through Claude CLI 2.1.270 with the exact patched GC candidate. This scoped
pass does not certify stock GC or replace native Claude/Codex and macOS gates;
diagnostic subsets and supplemental proofs retain their incomplete status.

Complete the gate in a retained, task-owned BB/GC environment. Pin the pack
artifact hash, released BB build, GC commit and binary hash, and both runtime
versions. Verify those identities through the running services before cases
execute. Test the exact GC PR build separately from unchanged GC 1.4 releases;
a development-build pass cannot certify stock compatibility. Start each test
environment once; replace or interrupt processes only in cases that explicitly
exercise that behavior. Keep normal user BB and GC state outside every test.

| Required behavior | Action and evidence |
| --- | --- |
| Fresh install and upgrade | Install the packaged artifact into a fresh BB store, discover the provider through BB, then upgrade an isolated prior installation while preserving its settings, receipts, and conversation. |
| Native chat and launcher | Drive the rendered BB UI from New thread through a reply for personal/global, mapped project/global, and mapped project/rig paths with Claude and Codex. Include the normal configured mayor, not only the acceptance role. Assert exact selections and actual GC execution directory. |
| Reasoning | Exercise Agent default and each advertised choice; confirm the UI selection reaches GC creation and remains consistent on subsequent turns and resume. Reject unsupported changes visibly before another request is submitted. |
| Actual work | Require streamed text, complete multiline input including BB context, follow-up memory, a real tool-created artifact in the GC directory, and correlated successful completion. Read GC's structured transcript independently of BB. |
| Trust and permissions | Cover a fresh untrusted workspace, approve once, deny, repeated identical approval, and interruption at an approval through BB's UI. Assert the permitted command ran once and the denied command did not run. Include a workspace with underscores. |
| Lifecycle | Exercise busy follow-up, interrupt, idle release/restore, native agent suspension/resume, BB host/server interruption, and controlled GC supervisor replacement. Assert preserved conversation identity and no duplicate user turn. |
| Ambiguous outcomes | Interrupt real create/submit responses after GC accepts them; disconnect during streaming and interrupt a bridge while delivery is uncertain. The fault mechanism may drop transport, but must not fabricate provider replies. Assert retained receipts, visible uncertainty, and explicit recovery without blind resubmission. |
| Error presentation | Exercise real provider/startup failures and supported timeout paths; errors must be visible in BB and must not count as successful assistant answers. Missing credentials or unavailable inference leave the required gate incomplete. |

Run the browser journeys against the actual released BB frontend on Linux CI
and the macOS desktop integration. Reuse the same scenario assertions where
possible. A run produces a per-case pass/fail/blocked ledger tied to artifact
identities, screenshots or traces, BB events, GC request/session identities,
and proof-artifact hashes. Retain full private evidence locally and upload
only explicitly scrubbed reports. Skipped, blocked, timed-out, or unexecuted
required cases cannot produce an overall pass. Require the aggregate gate in
branch protection; keep stock-runtime compatibility failures visible until
the fixes ship in a supported GC release or compatibility is otherwise proved.

## Execution log

- Started parallel lifecycle/recovery, launcher/discovery, and installer work.
- Installed locked pack dependencies in the active checkout.
- Prepared isolated BB 0.42.1 runtime under `/var/folders/6k/xzgngnms6jg4_z2l40y0_9vh0000gn/T/bb-gc-production-99l42_do`; GC 1.4.1 binary was previously downloaded and checksum-verified under `/var/folders/6k/xzgngnms6jg4_z2l40y0_9vh0000gn/T/gc141-bb-review-949mwtrw/gc`.

- Implemented lifecycle ownership/recovery, staged installer, project launcher,
  matching-workspace default and diagnostics. Final local checks: 31 provider
  tests; 12 installer/CLI tests each against GC 1.4.0 and 1.4.1; all plugin
  entries built by actual BB 0.42.1. Browser checks covered desktop/mobile,
  missing-path errors, retry and preserved exact selection.
- Live testing discovered and fixed rejection of BB's default service tier and
  personal-project unmanaged-workspace creation. It also confirmed blockers:
  GC 1.4.1 Codex activity stays unknown, and the current Claude TUI path can
  record a truncated submitted prompt. Full model-backed acceptance and
  registry publication remain pending; those requirements were not waived.
- Detailed evidence: [live verification](../research/bb-live-verification-2026-09-06.md).

- Added the exact GC 1.4.1 core import and repeated fresh global/rig launches.
  The rig completed one actual BB turn. Its second turn executed the requested
  shell write/read, but complete-prompt correlation failed because leading
  text was missing. Busy follow-up rejection was verified in actual BB events.
  The global case also reproduced truncated delivery. Live approvals,
  interrupt/release and restart/resume remain uncertified.

- Added a real conversation harness and a four-entry GC/runtime CI matrix.
  The aggregate check requires every live job; credentials and inference are
  mandatory. Long-prompt first-turn markers, second-turn memory, successful
  BB tool events, file contents and correlated completions are assertions,
  not fixture assumptions. Sixteen guard tests reject false acceptance,
  including truncated BB context when user markers survive. The harness also
  reads GC transcripts independently of the bridge's completion claim.
  Claude uses existing Manifold inference configuration; Codex CI needs the
  `BB_CODEX_API_KEY` secret, which was absent during implementation. Broader
  lifecycle acceptance above remains outstanding.

- Fresh automated GC 1.4.1 / BB 0.42.1 smoke runs failed for both runtimes,
  for both global and rig scopes. Claude's global terminal received only
  `n.` from the long submitted prompt; BB failed both scopes instead of
  reporting completion. Codex global failed on unknown activity; its rig
  failed the busy-session startup preflight. These are failed acceptance runs,
  not successful verification. Reports were preserved under temporary
  `bb-acceptance-reports-*` directories. A BB child-reaping cleanup defect in
  the harness was corrected and independently retested with a fresh BB app;
  all task-owned panes were captured before stopping the disposable cities.

- Replaced repeated environment creation with one retained test city and BB
  server. GC remains running between pack/configuration changes; replacing its
  binary preserved all state. Controlled runtime experiments isolated Claude
  short-input loss, missing Codex activity/adapter wiring, Claude hook session
  identity loss, and a Codex resumed-terminal readiness race. Corrections are
  in the separate GC `fix/bb-live-runtime-compatibility` worktree, based on
  v1.4.1. Focused tests and `go vet` pass; the broad GC baseline failed, including
  an expired waiver reproduced on unchanged v1.4.1. See the
  [validation report](../research/gc-runtime-fix-validation-2026-09-06.md).
- Development build `.5` passed the retained Claude global two-turn/tool/full
  prompt checks. Claude rig exposed BB's 30-second `turn/start` response limit;
  Codex exposed an acceptance role inheriting graph-worker drain behavior.
  Explicit conversational test roles now resolve through actual GC for all
  four agents. These failures remain recorded; release acceptance is pending.
- Python installer/CLI/acceptance guards pass: 35 tests on GC 1.4.0 and 1.4.1.
  The harness uses narrowly reviewed native Codex hook trust, with five guards,
  and supports new turns in a selected existing BB thread without recreating
  services. Personal credentials and private runtime evidence remain local.
- Fixed BB's asynchronous turn acknowledgment and the overlapping stop/new-turn
  journal race; 37 provider tests and typechecking pass. On the retained GC
  development build, both Claude scopes and Codex rig passed complete two-turn
  conversations and tool artifacts. Codex global and controlled Codex resume
  failed transcript identity changes; no uncertain operation was resent. The
  existing runtime gates and publication remain pending.
- BB release/restore passed two fresh Claude turns in the same existing
  conversation. The live gate now additionally suspends only its verified
  idle agent, waits for reconciliation, then requires a third turn with the
  same provider identity and first-turn memory without tools. New guards
  reject conversation resets and reading the proof file to fake memory.
- Actual Claude manual-permission testing exposed obsolete GC menu detection,
  an unsafe hardcoded deny key on the new four-choice menu, and a false idle
  match after an ineffective interrupt. No approval was sent and no test file
  was created. These GC corrections and their live verification remain required.

- Final Python guards/CLI matrix: 39 tests pass on each released GC binary.
  Two more asynchronous ownership regressions reproduced old observer failures
  and old startup timers aborting a newer turn; all 39 provider tests and
  typechecking pass after binding callbacks to their originating controller.
- Development `.7` passed Codex three-turn/tool/agent-resume checks in both
  scopes, preserving all conversation identities and recalling memory without
  tools. Real Claude approve-once, deny, identical repeated approvals, and BB
  stop at an approval all passed in the retained city. Claude resume exposed
  another GC defect: the stale-key probe ignores configured transcript roots
  and clears a valid key. Fix and final validation remain in progress.
- Verified an existing Dashlane OpenAI project key using actual Codex 0.153.4
  inference in a fresh private configuration, then configured repository secret
  `BB_CODEX_API_KEY`. This removes the missing-secret blocker; unchanged released
  GC runtime defects still keep acceptance and registry publication blocked.

- GC corrections through `f7e64f0b4` are pushed for review in
  [draft GC PR #6106](https://github.com/gastownhall/gascity/pull/6106). Development
  `.8` passes both Claude three-turn/tool/resume cases. Longer existing Codex
  conversations expose historical usage/model fields disappearing beyond the
  tail-read window; a fresh Claude workspace exposes a changed trust-menu
  default. Those upstream corrections remain in progress, with original
  failed reports and all state preserved.
- Corrected first-input lifecycle docs and report-upload help. Registry-only
  changes now trigger the mandatory BB acceptance workflow too. Only the three
  named JSON reports are uploadable; raw evidence remains private.

- GC corrections through `55cfa4acc` are pushed in draft PR #6106. Development
  `.9` passes all five real conversation cases; an independent review verifies
  all 15 complete forwarded prompts and preserved identities. Four existing
  conversations survive the controlled GC binary replacement. BB, its store,
  the city and all prior evidence remain intact.
- Two completed remote Codex tool turns are recovered after explicit evidence
  review and release of their idle BB leases. Only receipt completion changes;
  no request is resent. A real mismatched-workspace case also fails before any
  input acceptance or GC submission.
- Pack CI at `2eb6424` fails the live matrix and aggregate. Codex never reaches
  reliable startup on the released binaries. Claude returns an identical
  unrequested response in all four scopes; safe native error classification
  is added without weakening acceptance. Publication remains blocked. Abrupt
  host/server loss, lost HTTP replies and interruption during delivery still
  need live fault-injection evidence. Controlled supervisor replacement,
  agent resume and reviewed recovery now have actual development proof.

- CI diagnostics at `252ac34` prove Claude's fixed response is native
  `authentication_failed` / HTTP 403 on the Manifold route. A direct Anthropic
  CI credential route is prepared but no other project's vault key is reused.
- GC `0ff2cfda0` fixes the branch's API readiness fixture and resource-census
  failures; the expired-waiver and missing-watchdog failures remain. GC
  `59382ce25` and the matching pack changes preserve terminal provider errors,
  settle failed receipts correctly and retain retry/uncertainty safeguards.
  Forty-six provider tests and full GC worker/sessionlog suites pass. An actual
  native Claude 403 record passes real GC projection and pack classification;
  its absent user record correctly prevents unproved delivery settlement.
  No retained GC/BB service was restarted for this follow-up.
- Final pack installation preserves previous versions and matches reviewed
  source hashes. Existing Codex global/rig threads pass all three fresh turns,
  tools and memory after idle BB release/restore and agent resume. Claude's
  three first turns fail on exact-correlated native rate limits (HTTP 429),
  despite verified full prompts and stable identities; none is resent.
  The retained `.9` GC lacks the separate native-error projection follow-up.
  This five-case gate fails; the earlier all-five pass is historical evidence.
  Neither GC nor BB is restarted. Latest GC `59382ce25` CI passes the changed
  packages but remains red on the unchanged expired-waiver ledger and the
  separate missing watchdog command. Release gates remain unchecked.

- September 7 reasoning follow-up: corrected the pack's `none`-only provider
  capability and empty model ladders, exposed native effort choices in both
  pickers, and forwarded creation-time `options.effort`. Persisted selections
  prevent later turns/resumes from silently changing effort; older receipts
  retain Agent default. All 51 provider tests and TypeScript checks pass.
  Installed source matches the local branch. In normal BB 0.42.1, the rendered
  mayor picker retains Medium and Claude additionally offers Max.
- Actual isolated BB thread creation with Medium returns HTTP 201. Browser
  launcher submission renders the fixture reply and retains Medium; the HTTP
  fixture records exactly one creation with the effort override and one submit.
  A subsequent High selection fails visibly without another GC request. These
  are BB artifact checks against simulated GC, not model-backed acceptance.
  Evidence: `/var/tmp/bb-reasoning-artifact-nrcs0atr/verification.md`.
- Separately, retained live development GC creates fresh session `gc-4338` in
  `/private/var/tmp/gc-effort-live-xnsil8xh/workspace` and reports effort High in
  both effective options and persisted template overrides, replacing default
  Extra High. No prompt or credential copy was needed; existing files were
  preserved. Evidence: `/var/tmp/gc-effort-live-xnsil8xh/evidence/persistence-result.json`.
  Neither GC supervisor nor normal BB was restarted. Only isolated BB needed
  Node26 because its Node22 installation had a missing library. Its data and
  prior logs were preserved, and its original connection config was restored.
  The broader model-backed and release gates above remain open.

- September 7 personal-thread failure: the user's ordinary native-picker
  conversation failed because BB mandates its own personal workspace while
  GC's global mayor uses the city directory. The earlier prepared-workspace
  checks missed this route, and the suggested unmanaged environment was not
  available to a personal thread. Personal global conversations now retain
  GC's execution directory, announce the separate file/diff views before
  submission, and append explicit workspace context after BB's instructions.
  Project workspace validation remains enforced. Five added regressions cover
  the personal path, project/rig boundaries, missing GC directory, and retry
  without duplicate creation or submission. All 56 tests and typechecking
  pass. Installed normal BB source: `install-R7kKKV`.
- Read-only inspection of the original failed thread found no journaled GC
  turn and no submitted `hello?` in its native history. Its already-running
  Codex session had completed initialization, but stock GC 1.4.0 still reported
  activity `unknown`. The workspace fix alone does not establish a working
  conversation. A local stock-1.4 runtime backport passed six GC package suites,
  real tmux input checks, and independent review. It changes runtime/history
  handling without changing stock supervisor startup, config, or builtin packs.
- Preserved 83,982 filesystem entries before replacing the normal supervisor;
  retained its original log separately to avoid startup log truncation. Both
  existing mayor PIDs and session identities survived. Normal BB stayed running.
  Explicit retry of the original failed turn completed with Medium reasoning:
  "Here. I’m initialized in `/Users/csells/chris-city` and ready." Verified the
  rendered BB reply, completed receipt, exactly one successful BB turn, and
  the full 1,397-byte forwarded prompt in GC's independent transcript.
  Local GC build: `1.4.0-local-runtime-fixes`, SHA-256
  `21ca91add48ee9a032b8ca1956e3c4a700624411567beb4aee82ba5214872d1d`.
  Evidence: `/var/tmp/bb-personal-workspace-fix-OQXhUk/repair-result.json`.
- Changed the existing live acceptance global case to use unbound
  `proj_personal` and BB's separately provisioned personal workspace; rig
  cases retain exact project/workspace checks. All full-prompt, tool, memory,
  and three-turn/resume assertions remain required. Thirty-one guard tests
  pass. This updated live CI matrix has not yet run; the repaired user turn
  proves this local Codex path, not the remaining Claude or release gates.

- Full-product gate implementation now covers an independently declared
  required matrix, the actual released browser and isolated macOS desktop,
  real permission decisions, process/transport faults, and retained installation
  changes. Diagnostic subsets cannot produce an overall pass. The candidate
  CI jobs remain separate from stock GC compatibility, and raw evidence stays
  private. The complete matrix has not passed.
- Native mapped-project testing exposed missing rig choices before BB creates
  its workspace and missing project identity at provider startup. The pack now
  exposes configured mapped rigs in that catalog and resolves the project from
  the actual execution directory. Two regressions fail before the correction;
  all 58 provider tests and typechecking pass afterward.
- Retained Claude run `claude-673-core-02` passed eight cases: personal chat,
  mapped rig chat, release/restore, agent resume, approve once, repeated
  approval, underscore workspace, and mismatched-workspace rejection. It failed
  denial because the test incorrectly demanded an assistant reply after native
  rejection; that assertion now checks the actual denied tool and later memory.
  The other failures exposed Claude's unrecognized tool-interruption marker
  and the approval form's distinct Cancel control. All original evidence is
  retained under `/var/tmp/bb-full-e2e-u9mbwfem`.
- GC candidate `99bfa67c392f1007aefef79d3ebd61628383548c` includes focused fixes
  for nested Codex completion errors, uncertain fast-submit confirmation,
  explicitly requested singleton startup, and the exact Claude interruption
  markers. The controlled replacement preserved all 44 existing native pane
  PIDs; the original stuck interrupted transcript now reports idle without a
  resend. Required hooks and affected-package regressions pass. The broader
  fast suite passed nine of ten jobs; its remaining job failed in unchanged
  packman heartbeat and exec cancellation tests. The latter passed on a focused
  rerun; the former still fails. This is not a green full-suite claim.
- Fresh Codex provider-error testing exposed first-launch hook materialization
  changing the configuration fingerprint and draining the new session before
  a prompt could be submitted. No provider error was certified by that run.
  The ordering correction and remaining live cases are still in progress.

- September 19–20 isolated Hillsboro qualification PASSED on the Kimi route. Completion-11
  pins BB 0.43.3, SDK 0.4.104, Claude CLI 2.1.270, and GC
  `4f41f8285070d3509dae94cd97509eb562f2f068`. Automated checks pass:
  193 Python checks without skips against raw released GC 1.4.2 and 29
  browser/desktop guards. The plugin is identical to completion-8, preserving
  its 61 provider tests, TypeScript, and CLI build checks. Critical lost-submit-response, streaming-disconnect, and
  interruption cases passed. Completion-7 also passed lost-create-response and
  uncertain-delivery bridge recovery with the same exact plugin and GC hashes.
  Completion-7's full run stopped after three passing chat cases to pin the
  final CLI advice correction. The complete snapshot-8 matrix finished with
  37 passes, three failures, zero blocked, and zero unexecuted cases.
- Completion-4 retains 22 passing Kimi cases, 13 failures, and five unexecuted
  cases. Its independent native diagnostic subset retains nine passes and two
  failures. Later denial supplements on both routes prove the rejected tool
  did not run and the same conversation could continue; they do not rewrite
  those failed ledgers. Completion-5 stopped after one passing case when a GC
  interruption-marker defect required a new pinned binary.
- Completion-7 includes the GC interruption correction and explicit BB
  `provider.error` rendering; its plugin is unchanged from completion-5/6.
  Earlier correlated failed-turn settlement did not prove a visible error row.
  The fresh native invalid-token diagnostic now passes actual rendered-error
  proof, one failed completion, one create/submit, and no retry. A separate
  bridge-crash diagnostic exposed an assertion comparing JSON-escaped text;
  completion-7 fixes that guard without changing the plugin and passed the
  subsequent bridge-recovery diagnostic. The original critical ledger remains
  three passes, one failure, and 36 unexecuted cases; the separate recovery
  ledger has two passes and 38 unexecuted cases. Stock-GC
  Claude/Codex CI, macOS desktop,
  full native Claude/Codex acceptance, and registry publication gates remain open; current artifact
  hashes and retained evidence are in the
  [Hillsboro report](../research/bb-hillsboro-verification-2026-09-19.md).

- Completion-8 changes only the CLI bind confirmation from completion-7:
  allow ordinary catalog refresh for up to ten minutes; `gc bb agents` always
  discovers afresh. It no longer incorrectly promises immediate refresh after
  restarting BB. The reviewed deployment proposal is prepared but not activated.
  A passing full run, original compatibility gates, and publication remain pending.

- Completion-9 corrects two harness causes behind snapshot-8's three failures:
  a disappearing process during BB host restart (with a dependent server
  restart failure), and the busy composer's appended queue shortcut plus Linux
  Ctrl/Enter mapping. Ownership checks remain strict, with an actual Linux
  zombie-child regression. All four focused cases passed: personal chat, both
  BB restarts, and busy follow-up. The full snapshot-9 matrix then finished
  with 39 passes, one GC binary replacement failure, zero blocked, and zero
  unexecuted cases. That remaining failure exposed a race with the fixture
  service manager's automatic controller restart; the manager-aware correction
  is recorded in the snapshot-10 entry below. The deployment proposal remains unactivated,
  all original ledgers are retained, and overall qualification remains pending.

- Completion-10 changes only the lifecycle case module and its tests from
  snapshot-9. The manager-aware correction passed independent review, all 36
  Linux lifecycle guards, and the full 192-check Python suite without skips.
  The plugin, browser harness, and GC binary remain unchanged. Targeted personal
  conversation, GC controller restart, and binary replacement all passed;
  37 omitted cases remain unexecuted in that subset. The full matrix finished
  with 39 passes and one failure in approval interruption: Kimi requested an
  unprompted startup directory listing, and the provider failed closed before
  submitting the BB task. The requested tool never ran. The original failure
  and pending native operation are preserved, without approval or resend.
  Scrubbed ledgers: [full run](../research/bb-hillsboro-evidence-2026-09-19/completion10-summary.json)
  and [focused lifecycle](../research/bb-hillsboro-evidence-2026-09-19/completion10-gc-lifecycle-summary.json).

- Completion-11 changes only three test files: the shared startup prompt now
  explicitly requires `Ready.` without tools or workspace inspection, and the
  approval-wait guard captures an already-failed turn immediately, with a
  regression test. All 193 Python checks pass on Hillsboro without skips.
  The provider and GC artifacts are unchanged; the GC [source patch](../research/bb-hillsboro-evidence-2026-09-19/gc-1.4.2-bb-runtime-4f41f8285070.patch)
  remains available. The new focused approval-interruption fixture passed,
  leaving 39 cases unexecuted ([scrubbed summary](../research/bb-hillsboro-evidence-2026-09-19/completion11-approval-interrupt-summary.json)).
  The fresh full matrix passed all 40 required cases, with zero failed,
  blocked, or unexecuted ([full ledger](../research/bb-hillsboro-evidence-2026-09-19/completion11-summary.json)).
  The corresponding deployment proposal at
  `/tmp/bb-gascity-deployment-review-ppt6o__j` has 14 proposed files and 121
  artifact pins. Deployment and read-only production verification passed. The scoped
  Hillsboro Kimi gate is complete; original compatibility gates, complete
  native Claude/Codex matrices, macOS, and registry publication remain open.

- The exact GC candidate `4f41f8285070d3509dae94cd97509eb562f2f068`
  now passes its normal pre-push command, `make test-fast-parallel`: eight
  jobs passed, zero failed, exit 0 in 320 seconds. Runner corrections use
  pinned OSS `bd` 1.3.0, a short disk-backed `TMPDIR`, real `HOME`, and isolated
  test `GC_HOME`; no source changes were required. Normal pre-commit checks,
  including full vet, passed for this exact commit. The
  [normal-hook summary](../research/bb-hillsboro-evidence-2026-09-19/gc-normal-hook-summary.json)
  records the result and preserved prior failures. Herdr was unavailable and
  its capability-dependent coverage remains explicitly waived. This result
  does not claim `make check`, the broader integration suite, Herdr coverage,
  or registry publication; earlier failed ledgers remain unchanged. The exact
  candidate was subsequently pushed with the normal hook passing, as recorded
  in the [publication summary](../research/bb-hillsboro-evidence-2026-09-19/gc-publication-summary.json).

- Review branches are published: provider commit `0a9d6f0` in
  [draft PR #455](https://github.com/gastownhall/gascity-packs/pull/455) and
  GC candidate `4f41f8285070` in
  [draft PR #6481](https://github.com/gastownhall/gascity/pull/6481).
  The [retained CI observation](../research/bb-hillsboro-evidence-2026-09-19/ci-35522219285-summary.json)
  records three passing build/fixture/CLI jobs and six failed stock-GC live
  jobs, with selected-host mismatches and native Claude HTTP 403 errors.
  It does not establish a current Codex quota failure. Candidate jobs were
  still running at that observation. The plan stays open for its remaining
  release requirements.

- Hillsboro deployment is complete. The
  [production verification](../research/bb-hillsboro-evidence-2026-09-19/deployment-verification.json)
  passes all 121 artifact pins, six conversation-role prompts, running GC
  executable identity, BB 0.43.3 and 32 installed source files, connections,
  bindings, global/mapped-rig catalogs, private Kimi permissions, suspended
  duplicate aliases, and stable service identity. Both production services are
  active; enterprise `bd` 1.1.0 is unchanged. The backup is
  `/home/ubuntu/bb-gascity/backups/deployment-20260920T162634-hjxf6rqa`.
  No inference was submitted against production user state; all 40 model and
  fault cases ran in isolated state with the exact deployed artifacts. Public
  release requirements remain open, so this plan is not archived.
