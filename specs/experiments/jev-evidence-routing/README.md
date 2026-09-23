# Jev evidence routing experiments

Status: live paired evidence pilot and held-out evaluation completed. Both
arms matched all final labels; the held-out Jev-plus-fallback arm used 85.7%
fewer Claude tokens and 75.7% less assessment time on seven synthetic cases
repeated twice. Full-build benefit is still unmeasured; baseline 005 failed,
and the local-origin repair and latch routing need full-workflow validation.
See [measured results and limitations](RESULTS.md).

**Correction, 2026-09-23.** Earlier records described several full-build
failures as new Gas City or Beads bugs. They were not. The tmux orphan-reaper
failure is a known bug already fixed on Gas City `main` (a6b72d832, #5392) but
not in v1.4.2. The Beads forced-init preflight is a latent issue that only
appears when migrations exceed five seconds, which happened here under heavy
host load. The `do-work` latch closure relates to an upstream fix not in v1.4.2
(449df7c4a, #5900/#5901) plus a pack-side claim/template gap. The remaining
failures (remote inheritance, Claude config/trust, missing `origin`, dispatch
and workflow timeouts) were caused by the harness; the gate PyYAML failure was
environmental, with its exact cause unestablished. No full build
reached a Jev decision stage, so none of these results bears on Jev. The harness
is being reworked to follow the documented operator path. Details are in the
[RESULTS.md correction summary](RESULTS.md).

## Objective

Compare the Gas City pack with and without optional Jev evidence checking on
LLM token consumption, independently measured output quality, and elapsed time.
Use subscription-authenticated Claude/Codex CLIs for generative model work, not
paid generative-model API endpoints. Jev access requires its credential; generative Claude runs use the existing subscription.

## Reproducibility contract

- Starting repository revision: `05031f2c66e080865c379ff799c7369430560a8f`.
- Branch: `experiment/jev-evidence-routing`.
- Preserve each run's input, prompt, configuration, raw model output, token
  usage (including cache reads/writes separately), timestamps, terminal status,
  test results, and resulting artifacts. Never overwrite a previous run.
- Record exact resolved model versions, CLI versions, code/input hashes, and
  run order. Do not compare runs using different runtime versions as one cohort.
- Use matched tasks, fresh workspaces/sessions, fixed model/effort settings,
  and counterbalanced A/B ordering. Both arms receive the same task and proof.
- Quality comes from predefined expected classifications and executable tests,
  not Jev's confidence or the worker's self-assessment. Evaluation expectations
  remain outside the worker's input. Report false approvals separately.
- Include Jev latency and usage in the treatment totals. Report generative LLM
  tokens separately from Jev tokens. CLI dollar estimates are not subscription
  charges and are not the principal cost measure.
- Retain failures, invalid outputs, retries, timeouts, and missing telemetry.
  Missing usage is unknown, never zero. A failed run is not a speed win.
- Keep focused decision/review measurements separate from complete Gas City
  build measurements. Do not extrapolate component speedups to full builds.
- Tune on pilot cases only; freeze the treatment before evaluating held-out
  cases. A small pilot is exploratory, not evidence of general superiority.

## Ledger

See `ledger.jsonl` for append-only setup and experiment events. Run artifacts
will be linked from the results document when available. No credentials may
appear in any experiment artifact. Usage-bearing task transcripts (all matching task JSONL files for baseline 005) are also
archived locally under ignored `raw-transcripts/` directories; committed manifests
record their source paths and SHA-256 hashes.

## Initial observations

- Existing canonical checkout is on `bb-ux`, with untracked `bb-ux/` work;
  experiments use a separate worktree.
- Initial installed versions: Gas City 1.4.1; Beads 1.2.2.
- Latest GitHub releases observed: Gas City 1.4.2; Beads 1.3.0.
- Claude CLI reports a logged-in Claude Max subscription.
- Initial TypeSafe/Jev credential searches found no match. On September 20,
  Chris supplied the exact Dashlane note title, and live access was verified.
  The key is injected into process memory; it is not saved in the repository.

## Kind triage

A separate [kind-triage protocol](KIND-TRIAGE.md) tracks support for Julian's
maintainer-city approach. Its historical backtest uses frozen reference kinds;
priority and adopt-pr complexity are not automatic replacement candidates.
The [paired real-data evaluation](KIND-RESULTS.md) is complete: 31/32 raw
agreement with Opus 5 at maximum effort, 32/32 final agreement after seven
fallbacks, 77.9% fewer Claude tokens and 71.2% less classification time.
Keep these results separate from evidence review and full-build cohorts.
