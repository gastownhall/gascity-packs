# Verification and release status

The pack remains a release candidate. Fixture, CLI, installation and launcher
checks pass; model-backed acceptance is blocked on the runtime cases below.
No registry release has been published for this hardening change.

## Versions exercised

- Gas City 1.4.0 and 1.4.1: actual CLI pack loading, lint and command contracts.
- BB 0.42.1: actual server/host/frontend build, installation, upgrade,
  registration, browser launcher and thread creation.
- Plugin SDK 0.4.47; Node 22; Chrome via Playwright.
- Live GC 1.4.1 with Codex CLI 0.153.4 and Claude Code 2.1.263.

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
   delivery issue requires diagnosis in GC/Claude before certification.
3. **Transcript discovery:** custom provider configuration directories need
   GC `[daemon].observe_paths`. Current Claude replaces underscores in project
   directory names; GC 1.4's slug encoder does not. Use a compatible canonical
   workspace path when reproducing, and verify structured history directly.
   Shared workspaces also need stable provider session identities; do not
   work around ambiguous history by attaching the newest transcript.

The core-enabled rig agent completed one full turn through BB. Its second
turn executed the requested tool and created the expected file, but truncated
input prevented verified completion. A busy follow-up was correctly rejected.
Two-turn completion, live approval/denial/repetition, interrupt/release, and
restart/resume must still pass end to end for supported
runtimes before registry publication. Fixture coverage is not a substitute.
See [the evidence report](../../specs/research/bb-live-verification-2026-09-06.md)
for concrete observations and the [plan](../../specs/plans/0001-bb-production-readiness.md)
for outstanding gates.

## CI acceptance

The `BB end-to-end acceptance` check requires both the build/fixture/CLI matrix
and real Claude and Codex conversations on GC 1.4.0 and 1.4.1. Each live job
starts a new BB 0.42.1 server and host, imports the matching released GC core,
installs this checkout, and exercises both a global and a rig agent. It requires:

- A completed first turn that returns markers from both ends of a multiline
  prompt longer than 1 KiB.
- A completed second turn in the same GC session, with a successful BB tool
  event and a new file containing a word remembered from the first turn.
- Exact provider, agent, project, host and workspace selection, and correlated
  BB request, acceptance and completion events. An answer alone cannot pass.
- Independent GC transcript and receipt checks proving the full forwarded
  prompt, including BB's context, arrived as a new user message and the
  session is reliably idle. Preserved user markers cannot hide lost context.

Claude CI uses the repository's Manifold credentials and configured models with
Claude Code 2.1.263. Codex CLI 0.153.4 requires the `BB_CODEX_API_KEY` repository
secret. Missing credentials (including on fork PRs), timeouts, failed or
interrupted turns and skipped jobs cannot make the aggregate check pass.
No `pull_request_target` job exposes credentials to fork code.

This is the basic conversation gate. Live approval/denial/repetition,
interrupt/release and restart/recovery certification remain separate outstanding
release requirements; passing this smoke gate does not waive them. Configure
branch protection to require `BB end-to-end acceptance` if merges must be
enforced by GitHub; defining a workflow alone does not change branch protection.

To run the same live gate locally, provide inference credentials explicitly
and the released binaries on `PATH` (Node 22, tmux and the selected runtime):

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

Only `summary.json`, `global/report.json` and `rig/report.json` are CI artifacts.
Raw command captures under `private/` and the separate temporary state directory
can contain credentials and must not be uploaded. The workflow uploads only
those three explicitly named reports.

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
