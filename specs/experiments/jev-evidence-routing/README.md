# Jev evidence routing experiments

Status: implementation and baseline pilots complete; approved full-build Claude attempts recorded; a macOS runtime defect is locally fixed and verified. Paired Jev evaluation awaits its credential.
See [measured results and limitations](RESULTS.md).

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
appear in any experiment artifact.

## Initial observations

- Existing canonical checkout is on `bb-ux`, with untracked `bb-ux/` work;
  experiments use a separate worktree.
- Initial installed versions: Gas City 1.4.1; Beads 1.2.2.
- Latest GitHub releases observed: Gas City 1.4.2; Beads 1.3.0.
- Claude CLI reports a logged-in Claude Max subscription.
- No TypeSafe/Jev credential found by title searches of Dashlane passwords
  and secure notes. No API requests to Jev have been made.
