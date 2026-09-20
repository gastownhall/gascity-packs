# Verification and release status

The pack remains a release candidate. Current Hillsboro qualification uses
BB 0.43.3, SDK 0.4.104, Claude CLI 2.1.270, and a patched GC 1.4.2 candidate.
All 40 required live cases passed on the Manifold Kimi route through Claude
CLI 2.1.270, with zero failed, blocked, or unexecuted cases. The
[full snapshot-11 ledger](../../specs/research/bb-hillsboro-evidence-2026-09-19/completion11-summary.json)
pins provider `b17e84154ec3…` and GC `4f41f8285070…`. Those artifacts are now
deployed on Hillsboro, and [production verification passed](../../specs/research/bb-hillsboro-evidence-2026-09-19/deployment-verification.json):
all 121 pins, six role prompts, live service identities, installed provider
source, private configuration permissions, and global/mapped-rig catalogs.
Both services are active; enterprise `bd` 1.1.0 remains unchanged. The verifier
submitted no production inference; the full model matrix used isolated state.
Original configuration and state were backed up. No registry release has been published.

Completion-11 passes 193 Python checks without skips against released GC 1.4.2.
The unchanged browser driver retains 29 passing browser/desktop guards.
Its plugin is identical to completion-8, whose
61 provider tests, TypeScript, and CLI build pass. The GC candidate remains
`4f41f8285070d3509dae94cd97509eb562f2f068`.

That exact GC commit also passes its normal pre-push command,
`make test-fast-parallel`: eight jobs passed, zero failed, exit 0 in 320 seconds.
Pinned OSS `bd` 1.3.0, a short disk-backed temporary directory, real `HOME`, and
isolated test `GC_HOME` corrected the runner without source changes. Normal
pre-commit checks, including full vet, passed. The
[normal-hook summary](../../specs/research/bb-hillsboro-evidence-2026-09-19/gc-normal-hook-summary.json)
retains this result and the earlier failed-run evidence. Herdr was unavailable;
its capability-dependent checks remain explicitly waived. This is a passing
normal fast suite; `make check`, broader integration, and Herdr coverage remain
separate. Review-branch publication is recorded below.

The complete snapshot-8 matrix finished with 37 passes and three failures.
Those failures exposed a process-exit race with a dependent restart failure,
and a browser queue-control mismatch. Snapshot-9 corrects those harness paths,
including a real Linux zombie-child regression. Its four focused restart/queue
cases passed. The full snapshot-9 matrix then finished with 39 passes and one
failure in GC binary replacement: the harness raced the fixture's service
manager. Snapshot-10's manager-aware harness correction passed independent review and
36 Linux lifecycle guards. Its targeted GC lifecycle run passed all three
selected cases, leaving 37 unexecuted. Its full matrix finished with 39 passes
and one failure: Kimi requested a directory listing during startup before the
approval-interruption task could be submitted. The provider correctly failed
closed, and the requested task's tool did not run. Snapshot-11 changes only
three test files: explicit tool-free startup instructions and an approval-wait
guard with its regression test. A focused new approval-interruption fixture
passed, leaving 39 cases unexecuted in that subset. The subsequent fresh full
matrix passed all 40 cases. The earlier failed ledgers remain unchanged.

The scrubbed [full snapshot-10 ledger](../../specs/research/bb-hillsboro-evidence-2026-09-19/completion10-summary.json)
and [targeted lifecycle ledger](../../specs/research/bb-hillsboro-evidence-2026-09-19/completion10-gc-lifecycle-summary.json)
retain those results. The separate [snapshot-11 approval-interruption proof](../../specs/research/bb-hillsboro-evidence-2026-09-19/completion11-approval-interrupt-summary.json)
retains its incomplete aggregate status. The candidate's [source patch](../../specs/research/bb-hillsboro-evidence-2026-09-19/gc-1.4.2-bb-runtime-4f41f8285070.patch)
records the GC changes; it does not certify unchanged released GC.

The retained completion-4 Kimi ledger has 22 passes, 13 failures, and five
unexecuted cases. Its passes include personal and mapped-project conversations,
tools, full-prompt correlation, BB release/restore, agent resume, and all six
reasoning choices. Native diagnostics have nine passes and two failures;
separate denial supplements passed on both routes without rewriting those
failed ledgers. Native Claude's earlier tool follow-up was refused upstream and
was not retried. The pack now emits visible `provider.error` events as well as
failed turn settlement. A fresh native invalid-token diagnostic passed with a
rendered error, one failed completion, and no retry.
See the [current Hillsboro report](../../specs/research/bb-hillsboro-verification-2026-09-19.md)
for pinned artifacts, evidence, and remaining work.

The implementation is published for review in
[provider draft PR #455](https://github.com/gastownhall/gascity-packs/pull/455)
(commit `0a9d6f0`) and
[GC draft PR #6481](https://github.com/gastownhall/gascity/pull/6481).
The [GC publication record](../../specs/research/bb-hillsboro-evidence-2026-09-19/gc-publication-summary.json)
confirms the exact candidate and a passing normal pre-push hook. Complete
native Claude/Codex matrices, stock-GC CI, macOS qualification, and registry
publication remain open. The retained [current CI observation](../../specs/research/bb-hillsboro-evidence-2026-09-19/ci-35522219285-summary.json)
has three passing build jobs and six failed stock-runtime live jobs, with host
selection mismatches and native Claude HTTP 403 errors. It contains no current
Codex quota evidence; candidate jobs were still running at that observation.

The sections below preserve the earlier qualification history. Their BB
0.42.1 / GC 1.4.0–1.4.1 results do not certify the current installation or the
unchanged GC 1.4.2 release. Earlier real Claude and Codex conversations used
the GC corrections in [draft PR #6106](https://github.com/gastownhall/gascity/pull/6106).

## Earlier versions exercised

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
remaining release gates. At that earlier revision the GC baseline was red;
its broad pre-push check was explicitly bypassed for that review branch after
focused tests and normal pre-commit checks passed. This historical result does
not describe the current candidate's passing normal fast suite recorded above.
See the
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
it does not certify the unchanged released binaries. The separate GC candidate
CI job uses this flag; the stock release jobs do not.

## Full product gate

The conversation gate above is only part of product acceptance. The full gate
drives the released BB frontend, checks GC's native history independently, and
requires every case in `bb/tests/e2e_matrix.py`. A diagnostic subset always
leaves the overall report incomplete. Missing credentials, timeouts, skipped
cases and absent implementations cannot count as passes.

Install the locked browser driver dependencies once:

```sh
npm ci --prefix bb/tests --ignore-scripts
```

For an already prepared, marked scratch installation, reuse its manifest:

```sh
python3 -u bb/tests/full_e2e.py \
  --environment-manifest /absolute/path/to/environment.json \
  --report-dir /absolute/path/to/new-full-report-directory \
  --channel chrome
```

The manifest identifies the isolated BB store, GC home, plugin state, host,
projects, configured agents, credential environment file and exact binaries.
The runner verifies installed pack source, BB/runtime versions, GC commit and
binary hash before executing. It retains all state and private evidence.
Do not construct a manifest pointing at normal user services or data.

For first-time CI preparation, pass `--runtime`, `--gc-bin`, `--gc-commit`,
`--bb-bin` and `--bb-app-bin` instead of a manifest, with the credentials
described above. Development builds also need `--gc-development-base`.
This prepares one isolated installation and retains it for the matrix. Linux
CI installs Playwright's pinned Chromium; local `--channel chrome` uses Chrome.
Only explicit lifecycle cases replace verified test processes. Fresh-install
coverage creates a separate BB store while reusing the same GC controller.

On macOS, `desktop.native` is required. Prepare a copy of the released app with
`desktop_app.py`, attach it with `desktop_attach.mjs`, and set `desktopSpec` in
the manifest to the resulting `desktop.json`. The helper gives the copy its
own profile, cache and bundle identity, verifies the production app archive,
and attaches to the isolated BB endpoint. It never launches the user's app
profile. The desktop journey uses the same completion and native-history
assertions as the browser.

Run both Claude and Codex manifests against the candidate being reviewed.
Keep `summary.json` and its artifact identities with the validation result;
raw screenshots, traces, event streams, credentials and command captures under
`private/` stay local. The CI candidate jobs upload only their scrubbed
summary and require an entirely passing ledger. Branch protection must
separately require the aggregate check. A candidate pass does not certify an
unchanged GC release or imply that branch protection is configured.

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
