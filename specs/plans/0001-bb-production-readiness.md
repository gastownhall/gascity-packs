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
- [x] Extend CI to the release matrix, review all changes, and run relevant final checks.
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
