# Jev kind-triage experiment

## Motivation and evidence status

Chris relayed Julian's report during this session: Jev now performs kind triage
in maintainer-city; kind/priority and initial adopt-pr complexity backtests had
mixed results except for kind, which had a **96% hit rate against Opus Max**.
This is a user-supplied report of agreement with the previous model, not an
independently verified accuracy score. Sample size, class distribution, exact
model versions, rubric, confidence cutoff, inputs, and raw backtest outputs were
not supplied. Do not pool this number with our experiments.

The pack now supports a separate kind-only decision. Priority and adopt-pr
complexity remain outside automatic Jev replacement. The implementation uses
the public Gas City policy; Julian's exact maintainer-city implementation was
not available. Repository-specific label mapping is explicit.

Current measurement status: one live synthetic kind preflight succeeded with
Jev 1.13.0; its response contract, usage and timing are recorded in
[live-jev-preflight-001](live-jev-preflight-001/report.json). This is an access
check, not a replication of 96% or measured kind savings. Offline contract
checks and synthetic routing tests establish software behavior only. The full-build
failures in [RESULTS.md](RESULTS.md) remain unresolved as comparative evidence.

## Historical backtest

Use `scripts/jev_kind_backtest.py` with a frozen JSON dataset:

```json
{
  "schema": "gc.kind-backtest.v1",
  "reference_model": "exact resolved reference model version",
  "reference_effort": "recorded setting; do not infer from the name Opus Max",
  "reference_provenance": "path/URL and SHA-256 of archived reference outputs",
  "split": "pilot",
  "cases": [{
    "id": "repository-issue-or-pr-and-snapshot-id",
    "snapshot": {"title": "Frozen title", "body": "Frozen original body"},
    "reference": "bug"
  }]
}
```

Preserve original reference model output, rubric, input snapshot and collection
time alongside the dataset. Reference values use logical kinds `bug`, `feature`,
`docs`, `chore`; normalize `kind/enhancement` to `feature` explicitly during
import. Deduplicate the same issue/PR across pilot and held-out splits. Use the
same information cutoff for both models; a richer reference input makes this
a different experiment. Existing label fields and reference answers are never
included in Jev state; the helper allowlists title/body. Check for reference
answers embedded in collected bodies during dataset preparation.

```sh
# Validate and freeze inputs without any model call.
python3 scripts/jev_kind_backtest.py frozen-kind-pilot.json \
  --out /absolute/new/kind-validation --validate-only

# Requires the privately supplied TYPESAFE_API_KEY.
python3 scripts/jev_kind_backtest.py frozen-kind-pilot.json \
  --out /absolute/new/kind-pilot --model jev-1.13.0 --threshold 0.85
```

Each output directory is immutable. It contains the dataset, source copies and
hashes, model/settings manifest, filtered inputs, per-case exact requests, raw
responses, terminal reports, and summary. Failed attempts exit nonzero and
remain in the denominator. No hidden retries. Resolved model and token usage
are retained even if a returned decision fails validation.

The summary distinguishes:

- Agreement on answered cases: raw Jev/reference agreement, including decisions
  below the routing threshold. `unclear` does not match a reference kind.
- Agreement on routed cases: agreement for confident non-unclear decisions.
- Coverage: confident non-unclear decisions divided by all cases.
- Matching routed fraction of all cases: useful matching replacements divided
  by the entire dataset, including failures and fallbacks.
- Per-kind confusion matrix, failures, and fallbacks. A dominant class must not
  conceal poor behavior on less common kinds.
- Observed Jev input/output tokens and elapsed time. Missing usage remains
  unknown. Historical reference costs and LLM fallback costs are **not**
  measured by this runner; its timing is classifier timing only.

Tune only on pilot data. Freeze the question version, threshold, taxonomy,
model, dataset and importer before running held-out cases. Independently
adjudicate disagreements and a sample of agreements before making an accuracy
claim: matching Opus can reproduce an Opus error. Report sample size and class
mix next to every percentage.

## Paired subscription experiment

Historical agreement is the first check, not the A/B outcome. The next live
experiment should prioritize kind triage before another expensive full build:

1. Freeze the kind rubric and matching inputs. Record exact Claude model and
   effort from the original Opus run; “Max” may refer to a setting or plan, so
   preserve the actual configuration instead of guessing.
2. Baseline: classify kind with the logged-in Claude subscription CLI. Treatment:
   Jev first, then the same Claude kind classifier only for fallback cases.
   Preserve all prompts, outputs, per-model input/output/cache counters,
   versions, errors and timing. Never switch generative work to paid API keys.
3. Alternate order per matched case, repeat in fresh sessions, and include Jev,
   fallback, failure and retry time/tokens. Record machine load and cache state.
   Compare classifier time separately from complete issue-triage execution.
4. Compare adjudicated quality, agreement, per-kind errors, coverage, all LLM
   token categories, Jev tokens and paired elapsed times. Count subscription
   consumption, not CLI dollar estimates as actual charges.
5. Only then assess the full workflow with the same snapshots and public-write
   behavior disabled in an isolated fixture. Label writes require their own
   explicit authorization; neither this helper nor this experiment performs them.

The existing evidence A/B harness classifies evidence, not kinds. This kind
backtest runner evaluates historical references and does not yet implement the
paired Claude/fallback runner described above. Do not present its output as a
completed A/B test or an end-to-end speed result.

## Recorded software validation

[Contract smoke 001](kind-contract-001/verification.json) exercised the real CLI
with synthetic data: validation-only succeeded, missing credentials failed
with explicit fallback, and labels/reference fields were absent from the model
request. Live model calls: zero. These fixtures do not measure model quality.

[Relevant regression checks](kind-contract-001/focused-tests.txt): 71 passed,
176 subtests passed. The initial broader run had 159 passes and seven failures:
five subprocess dependency failures passed after placing the existing test
virtualenv on PATH; two claim-command tests still exceeded their two-second
limits. Both timeouts reproduced against unchanged commit `6e005f4` in a
separate extracted tree; see [baseline evidence](kind-contract-001/baseline-timeout-check.txt).
The broader suite is therefore not wholly green on this host. No claim-command
behavior or test timeout was changed for this extension.
