# Verification and release status

The pack remains a release candidate. Fixture, CLI, installation and launcher
checks pass. Earlier real Claude and Codex conversations passed locally with the GC
corrections in [draft PR #6106](https://github.com/gastownhall/gascity/pull/6106).
The final-pack check passes Codex but is blocked by native Claude rate limits;
acceptance against unchanged released GC still fails. No registry release has
been published for this hardening change.

## Versions exercised

- Gas City 1.4.0 and 1.4.1: actual CLI pack loading, lint and command contracts.
- BB 0.42.1: actual server/host/frontend build, installation, upgrade,
  registration, browser launcher and thread creation.
- Plugin SDK 0.4.47; Node 22; Chrome via Playwright.
- Released GC 1.4.0/1.4.1 and development GC `1.4.1-bb-live.9`
  (`55cfa4acc`), with Codex CLI 0.153.4 and Claude Code 2.1.263.

## Passing checks

The provider tests cover scoped catalogs, repeated approvals and denial,
steering errors, duplicate prevention, lease ownership, uncertain creation and
submit recovery, release/interrupt races, workspace validation, default service
tier, and prompt/transcript correlation. Installer tests preserve previous
sources and settings through failed builds and registrations.

The actual BB launcher creates threads with the exact selected global agent,
standard project, host and unmanaged workspace. Missing paths produce a
retryable validation error. Refresh preserves the exact agent. Desktop and
mobile dark-mode layouts were inspected; the mobile form has no horizontal
overflow. Personal projects are excluded because BB rejects unmanaged
workspaces there.

## Runtime blockers

1. **Codex completion:** the model returned the expected answer, but GC 1.4.1
   reports structured tail activity as `unknown`. Its released Codex metadata
   reader supplies usage/model information without activity. The bridge cannot
   safely infer completion from an assistant message and now fails explicitly.
2. **Claude prompt delivery:** the model returned the requested marker, and GC
   reported reliable idle history, but the recorded user input contained only
   the tail of the submitted BB context and prompt. The complete submitted
   text was absent. The bridge keeps this operation unsettled instead of
   treating the answer as proof of complete delivery. The underlying TUI
   delivery issue was reproduced: short unbracketed tmux input loses its
   prefix in current Claude, while bracketed paste preserves the complete
   prompt. The correction passes development-build tests; the released
   binaries still require it.
3. **Transcript discovery:** custom provider configuration directories need
   GC `[daemon].observe_paths`. Current Claude replaces underscores in project
   directory names; GC 1.4's slug encoder does not. Use a compatible canonical
   workspace path when reproducing, and verify structured history directly.
   Shared workspaces also need stable provider session identities; do not
   work around ambiguous history by attaching the newest transcript.
4. **First-input startup race:** a newly created session can still be processing
   its startup instructions. Treating empty/degraded history as permission to
   submit lost the first BB request in a live rig test. The pack must verify
   the workspace, then wait for reliable idle history before that submission.
5. **Claude approvals and interruption:** Claude 2.1.263's current approval
   screen is not recognized by released GC's parser. Its hardcoded denial key
   `3` selects “switch to auto mode” in the observed four-choice menu; “No” is
   `4`. The same menu's selected row can be mistaken for an idle prompt after
   an ineffective interrupt. These require GC corrections before approval
   support is safe; no approval was sent during the failed test.

The retained development environment passes all five conversation cases on
`1.4.1-bb-live.9`: Claude global, rig and an underscore workspace, plus Codex
global and rig. Each passes three turns, complete forwarded-prompt checks, a
real tool artifact, agent suspension/reconciliation, and tool-free memory recall
after resume with unchanged conversation identities. Four cases continue BB
threads retained across the GC binary replacement; BB and its store stayed
running throughout. The Codex cases also exercise continued log growth after
the historical usage/model metadata correction. The fresh Claude workspace
passes the corrected current trust-menu handling without manual trust seeding.

Real Claude approve-once, deny, repeated identical approvals, interruption at
an approval prompt, and BB release/restore have additional development evidence.
Two Codex turns that failed before the metadata correction were independently
proved complete and recovered after releasing their idle BB leases. Their
original request IDs were preserved and no prompt was resent. These results
do not certify unchanged GC 1.4.0 or 1.4.1, abrupt process-loss recovery, or the
remaining release gates. The full GC test baseline is also red; its broad
pre-push check was explicitly bypassed for the review branch after focused
tests and normal pre-commit checks passed. See the
[GC validation report](../../specs/research/gc-runtime-fix-validation-2026-09-06.md)
for the failures and limits.
See [the evidence report](../../specs/research/bb-live-verification-2026-09-06.md)
for concrete observations and the [plan](../../specs/plans/0001-bb-production-readiness.md)
for outstanding gates. [Root-cause experiments and development validation](../../specs/research/bb-runtime-root-causes-2026-09-06.md)
track the corrections separately from released-binary acceptance.

## CI acceptance

The `BB end-to-end acceptance` check requires both the build/fixture/CLI matrix
and real Claude and Codex conversations on GC 1.4.0 and 1.4.1. Each live job
starts a new BB 0.42.1 server and host, imports the matching released GC core,
installs this checkout, and exercises both a global and a rig agent. It requires:

- A completed first turn that returns markers from both ends of a multiline
  prompt longer than 1 KiB.
- A completed second turn in the same GC session, with a successful BB tool
  event and a new file containing a word remembered from the first turn.
- After suspending only that verified idle agent and waiting for controller
  reconciliation, a third completed turn must recall the first-turn word and
  preserve both GC and provider conversation identities. GC and BB stay running.
- Exact provider, agent, project, host and workspace selection, and correlated
  BB request, acceptance and completion events. An answer alone cannot pass.
- Independent GC transcript and receipt checks proving the full forwarded
  prompt, including BB's context, arrived as a new user message and the
  session is reliably idle. Preserved user markers cannot hide lost context.

Both test agents have an explicit conversational role that finishes startup and
waits for BB user messages. Leaving their role unspecified inherits core's graph
worker, which may correctly drain before receiving a conversational request.
The fixture keeps the core import and real runtime configuration; it does not
override the behavior of agents selected by production users.

Claude CI uses Claude Code 2.1.263 with `BB_CLAUDE_API_KEY` for direct Anthropic
access when configured, otherwise the repository's Manifold credentials and
model aliases. The direct-key route removes the Manifold endpoint, token and
model overrides. Codex CLI 0.153.4 requires the `BB_CODEX_API_KEY` repository
secret, configured after a real Codex API response check. Missing credentials (including on fork PRs), timeouts, failed or
interrupted turns and skipped jobs cannot make the aggregate check pass.
No `pull_request_target` job exposes credentials to fork code.

[CI at `252ac34`](https://github.com/gastownhall/gascity-packs/actions/runs/34074965026)
passes both build/fixture/CLI jobs and fails every live job. All four Claude
cases match native HTTP 403 errors classified as `authentication_failed` on
the Manifold route. Codex never reaches reliable startup on the unchanged
released binaries. The Claude credential/access issue and the GC runtime
corrections both need resolution before release. No direct Claude CI key has
been configured by this work.

The follow-up provider-error correction makes native terminal errors fail BB
turns and settle their receipts as failed, while preserving active retries and
later successful answers. Live settlement and reviewed recovery share the same
prompt, idle, text and tool guards. Forty-six provider tests pass, including
interruption/release races during failed settlement. These follow-up changes
have separate native-error and integration evidence; the five full development
conversation runs above used `.9` before this follow-up.

The final installed pack was then checked in those same five BB conversations,
after releasing only their verified idle bridge leases. Codex global and rig
pass all three fresh turns, tools and memory after agent resume, preserving
their earlier conversation identities. Claude's three cases fail their first
turn on native `rate_limit` errors, HTTP 429. Their complete 3,108-byte forwarded
prompts, receipt digests and unchanged identities are independently verified;
no request was resent. The retained GC remains `.9`, which lacks the subsequent
native-error projection and still presents those errors as assistant answers.
Thus this is a failed five-case gate, not final-pack Claude certification.
GC and BB were not restarted. Evidence:
`/private/tmp/bb-live-9dbgrsx5/current-pack-fivecase-ki6iozqc/summary.json`.

This is the conversation and agent-resume gate. Approval/denial/repetition and
interrupt/release have additional local development evidence; their released-runtime
certification and supervisor restart/recovery remain separate release requirements; passing this smoke gate does not waive them. Configure
branch protection to require `BB end-to-end acceptance` if merges must be
enforced by GitHub; defining a workflow alone does not change branch protection.

To run the same live gate locally, use Python 3.11 or later, provide inference
credentials explicitly, and put the released binaries on `PATH` (Node 22, tmux
and the selected runtime):

```sh
python3 -u bb/tests/live_acceptance.py \
  --runtime claude --gc-bin /absolute/path/to/gc \
  --bb-bin /absolute/path/to/bb --bb-app-bin /absolute/path/to/bb-app \
  --report-dir /absolute/path/to/new-report-directory
```

Claude accepts `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` or
`CLAUDE_CODE_OAUTH_TOKEN`; custom endpoints/models use the runtime's standard
environment variables. For `--runtime codex`, provide `OPENAI_API_KEY` or set
`BB_ACCEPTANCE_CODEX_AUTH_FILE` to an existing authorized auth JSON file. The
harness copies it into its private, disposable Codex configuration; it never
tests against the original runtime store. All workspaces, cities, BB stores,
ports and tmux sockets are separate from normal work. State remains available
after the harness stops its own services.

Codex 0.153.4 also requires trust for hook definitions, separately from workspace
trust. The acceptance harness seeds native trust for exactly four reviewed GC
hooks in its fresh configuration and verifies their definitions before launch.
Changed or additional hooks retain normal review requirements. This setup is
confined to the test harness; it does not change the pack's permission policy.

For repeated local checks, keep one isolated GC/BB environment running and call
`bb/tests/live_assertions.py` with its explicit host, project, agent, workspace
and private environment. Add `--existing-thread-id <id>` to exercise fresh turns
in an existing BB conversation. The checker excludes earlier events and still
requires full prompt delivery, correlated completion and the tool artifact.
An uncertain prior submission must be reviewed before another prompt can run.
Add `--exercise-resume` to suspend that verified test agent after its first two
turns and check the third turn's identity and memory. The self-contained CI
harness always enables this check. The checker never restarts either server.

Only `summary.json`, `global/report.json` and `rig/report.json` are CI artifacts.
Raw command captures under `private/` and the separate temporary state directory
can contain credentials and must not be uploaded. The workflow uploads only
those three explicitly named reports.

For an explicit GC development build, add `--gc-development-base 1.4.1` and
use a binary reporting a prerelease version such as `1.4.1-bb-live.1`.
Reports identify this as development validation and record the binary hash;
it does not certify the unchanged released binaries. CI never sets this flag.

## Reproduce the browser check

Use an isolated BB/GC installation and model credentials that you control.
Keep its cities, tmux socket, BB data directory, plugin configuration, journals,
provider configuration directories and ports separate from normal work.
The existing workspace must be on the chosen BB host, with a standard project
bound by `gc bb bind`. Install this pack with `gc bb install --yes` from that city.

With Playwright and Chrome installed:

```sh
node bb/tests/live_launcher.mjs \
  --url http://127.0.0.1:<isolated-BB-port> \
  --host <BB-host-ID> --project <BB-project-ID> \
  --model <exact-ID-from-gc-bb-agents> --workspace <existing-workspace>
```

Set `PLAYWRIGHT_MODULE` to an absolute module path if Playwright is installed
outside the project. Without `--prompt`, this checks validation and layout
without creating a model thread. Add `--prompt 'Reply exactly GC_CHECK'` to
create one thread; the command records its URL but does not claim model
completion. Inspect `bb thread log`, `bb thread output`, the GC structured
transcript, and the ownership receipt. Preserve artifacts after failures;
do not resend an uncertain prompt.
