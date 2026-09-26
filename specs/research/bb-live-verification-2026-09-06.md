# Live BB / Gas City verification — 2026-09-06

## Scope and outcome

This pass exercises the production-readiness branch against released BB 0.42.1
and Gas City 1.4.1, with 1.4.0 retained in CLI compatibility checks. It found and
fixed real integration defects beyond the initial HTTP fixtures. It does not
establish production readiness: runtime completion/delivery gates remain open.
No registry publication is justified by these results.

## Released versions

- [BB 0.42.1](https://github.com/get-bb/bb/releases/tag/v0.42.1), commit
  `a4aa07f9ee3fdeb5716a26a368246ea1ef9e0b78`; installed from `bb-app@0.42.1`.
- [Gas City 1.4.1](https://github.com/gastownhall/gascity/releases/tag/v1.4.1),
  commit `58ef17e3bd685fd5cf7f21286277b208d3324590`; downloaded Darwin arm64
  archive SHA-256 `019e5ae701531d5c080fdf99d2dc1e3c046ae76d2735918c4d94ecd5ed8ac7a0`.
- GC 1.4.0: `a7297c511d637a3609947386f3389d76ddb2f23b`.
- Plugin SDK 0.4.47, Node 22.23.2, Codex CLI 0.153.4, Claude Code 2.1.263.

## Isolation and artifacts

Task-owned BB/GC data, config, installations and logs are retained under:

`/var/folders/6k/xzgngnms6jg4_z2l40y0_9vh0000gn/T/bb-gc-production-99l42_do`

A later canonical Claude workspace is `/private/tmp/gc-bb-claude-p29w9qll`.
The regular user BB/GC installations were not used as test targets. Separate
ports were 49223 (BB), 49224 (host daemon), and 49225 (GC); the task's tmux socket
was `bb-live-99l42`. Provider authentication was isolated from user session
storage. Scratch contains credentials and must not be uploaded wholesale.

`run.py` and `test-env.json` in the scratch root preserve the command environment.
Browser evidence includes `launcher-desktop.png`, `launcher-mobile-error.png`,
`launcher-desktop-refreshed.png`, and per-run `first-thread.png`. The reusable
repository browser check produced separate artifacts under `bb-gc-launcher-*`.
`sanitized-results.json` records selected transcript metadata and prompt digests;
it is supplemental evidence, not a complete raw transcript.

## Findings fixed in the pack

- Actual BB supplies `serviceTier: "default"` even when a provider has no tier
  override. The previous truthiness check rejected every such thread before
  GC creation. Default is now accepted; nondefault overrides remain rejected.
- BB rejects personal-project unmanaged workspaces. The launcher now requires
  a standard project, listing its mapped city's global and rig agents together.
- Validation errors before thread creation are retryable. Errors during creation
  retain uncertainty and require explicit inspection before retry.
- A failed initial preflight now releases its local lease, permitting a safe
  retry of the same thread without creating another GC session.
- Unknown activity fails explicitly. Every turn, including after bootstrap,
  waits for a new user entry containing the complete submitted prompt before
  attributing an answer. Missing/truncated input cannot establish completion.

## Live observations and remaining blockers

### Codex completion

Thread `thr_4j522zi44b` selected the exact global `codex` agent on the configured
host and unmanaged workspace. After the default-tier fix, GC created `gc-1`,
accepted the prompt, and Codex emitted `GC_LIVE_ONE`. The runtime's actual rollout
file recorded a final assistant response and `task_complete`.

Once GC's `observe_paths` included the isolated Codex sessions directory, its
structured API reported non-degraded history with `tail_state.activity: unknown`.
The [released Codex tail reader](https://github.com/gastownhall/gascity/blob/v1.4.1/internal/sessionlog/codex_usage.go)
constructs metadata for model and usage without setting activity. This is an
upstream contract limitation, not evidence that the model failed to answer.
The pack cannot turn that unknown state into reliable completion. Later stopping
and GC lifecycle activity produced `gc-2`; do not treat it as the original session
or use its newer transcript as proof of `gc-1`'s outcome.

### Claude discovery and delivery

Threads `thr_bxqf5tshpi` / `thr_ytd55tkywt` launched the exact global `claude`
agent (`gc-3` / `gc-4`) and the model answered. GC initially exposed terminal
fallback. Custom config directories require `[daemon].observe_paths`; the
actual Claude project directory also replaces underscores, while GC 1.4's
[ProjectSlug implementation](https://github.com/gastownhall/gascity/blob/v1.4.1/internal/sessionlog/reader.go)
only replaces slash and dot. A canonical path alone did not fix that mismatch.

Attempts in a fresh `/private/tmp/gc-bb-claude-*` workspace first failed at
Claude's trust dialog; GC's startup handling selected exit. The scratch Claude
configuration was explicitly updated to trust this task-owned directory.

Thread `thr_rqcaggefdw` then reached actual GC session `gc-8`. Its structured
history was non-degraded and idle, and its assistant answer was `GC_CLAUDE_ONE`.
However, its user entry began `nt turn; future turns will run in the updated
environment.` followed by the final user request. The preceding BB context was
missing. The receipt hashes the complete submitted text, and bootstrap did not
find that text in history, so the bridge withheld completion and eventually
reported failure. The precise cause of this TUI truncation is not yet proven;
do not claim a GC/Claude fix or successful two-turn integration.

Multiple same-provider sessions sharing a work directory additionally require
stable provider session keys for unambiguous discovery. The first scratch city omitted the core pack. A follow-up imported the exact
1.4.1 core pack and repeated both global and rig cases in fresh trusted
workspaces. Global `verifyglobal` (`thr_5by4n29enu`, `gc-26`) still recorded only
the tail of its BB prompt. Rig `sample/verifyrig` (`thr_cuqmid849y`, `gc-27`)
completed its first turn through BB with the full prompt preserved and final
output `GC_CLAUDE_ONE`.

The rig's second prompt asked for a shell write/read of `live-proof.txt`. The
model created the file containing `GC_TOOL_OK`, but that turn's recorded user
input again omitted the leading context. The bridge withheld its output and
completion. A concurrent busy follow-up was rejected with `client/turn/rejected`
without submitting it or closing the original turn. Thus a core-enabled city
improves setup fidelity but does not eliminate the intermittent delivery issue.

The [released tmux sender](https://github.com/gastownhall/gascity/blob/v1.4.1/internal/runtime/tmux/tmux.go)
uses literal send-keys for short input and bracketed paste for longer buffers.
This is a lead for diagnosing multiline input delivery, not a verified root
cause. No padding, terminal escapes, or partial-prompt matching were added as
an unverified workaround.

### UI, installation, and diagnostics

Real `gc bb install --yes` staged dependencies and the helper, built all plugin
entries through BB, moved the registration, and activated the new version.
Repeated upgrades preserved prior versions and settings. Actual `gc bb status
--json` reported BB running, GC 1.4.1 reachable, a valid project binding and the
unsettled ownership receipts. GC discovers the commands' JSON result schemas.

The browser selected the exact host/project/global agent/workspace and created
BB threads without substituting defaults. Mobile dark-mode validation retained
the selected agent, displayed a missing-path error, enabled correction/retry,
and showed no horizontal overflow. Both global and rig launches were exercised. The rig completed one turn;
subsequent tool output was withheld when full-prompt correlation failed.

## Required continuation

Continue in the core-enabled isolated city to diagnose current Claude session
identity and complete multiline delivery behavior. Resolve or explicitly scope
out unsupported runtime activity with evidence, not inferred idle states.
Then complete global/rig two-turn conversations, tools, repeated approvals and
denial, queued/busy input, interrupt, release, restart/resume and recovery through
actual BB. The original production-readiness requirements remain unchanged.

Keep this branch at release-candidate status until those checks pass. Upstream
issue reports or code changes can use this evidence, but none were submitted by
this pass.
