# BB production readiness

## Objective

Finish the remaining work identified in [the assessment](../research/bb-production-readiness-2026-09-06.md) against released BB 0.42.1 (SDK 0.4.47) and GC 1.4.1. Retain GC 1.4.0 compatibility where verified. Build the dedicated Gas City launcher with existing BB extension APIs. Native BB Model picker changes and the explicitly listed richer v1 exclusions remain outside this pack change.

## Work and verification

- [x] Correct repeated approval handling, busy-turn steering errors, and stale workspace discovery, with regression tests.
- [x] Enforce durable ownership and safely reconcile uncertain creation/submission and crashed operations; test active/recovery races without blind resubmission.
- [x] Add a host/project/agent/workspace launcher that keeps exact selections, refreshes and reports errors, validates at execution, and uses BB's native styling.
- [x] Enforce matching workspaces for coding; make conversation-only mismatch an explicit supported choice.
- [x] Stage and validate upgrades before activation, retain previous installations, and exercise rollback failures while preserving config and journals.
- [x] Improve diagnostics and update user setup/recovery docs and compatibility declarations.
- [ ] Verify actual BB/GC installation and UI with isolated state: global/rig agents, two turns, tools, approval/denial/repetition, busy follow-up, interrupt/release, restart/resume, failures/recovery, and mismatched workspaces.
- [x] Extend build, fixture and CLI CI to the release matrix.
- [x] Pass retained development Claude global/rig/underscore and Codex global/rig three-turn/tool/resume checks, with full forwarded-prompt and stable-identity evidence.
- [ ] Pass actual Claude and Codex two-turn/tool acceptance in CI on GC 1.4.0 and 1.4.1; build/fixture success alone is insufficient.
- [ ] Commit/push the completed change and publish a versioned pack through the repository's release workflow only after release gates pass.

## Preservation and evidence

All running test services, cities, threads, installations, logs and generated outputs belong to scratch roots. Existing user BB/GC state is not a test target. Preserve uncertainty on ambiguous remote outcomes. Record actual verification outcomes below; fixture success does not substitute for live UI/model execution.

Initial implementation base: `b8b255256d7fc218e3a6854d5b2069c515c5c17f`.
Initial working tree: only the untracked assessment under `specs/research/`.

## Execution log

- Started parallel lifecycle/recovery, launcher/discovery, and installer work.
- Installed locked pack dependencies in the active checkout.
- Preparing isolated BB 0.42.1 runtime under `/var/folders/6k/xzgngnms6jg4_z2l40y0_9vh0000gn/T/bb-gc-production-99l42_do`; GC 1.4.1 binary was previously downloaded and checksum-verified under `/var/folders/6k/xzgngnms6jg4_z2l40y0_9vh0000gn/T/gc141-bb-review-949mwtrw/gc`.

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
