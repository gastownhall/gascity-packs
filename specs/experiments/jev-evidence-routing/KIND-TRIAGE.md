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

Current measurement status: the paired test on our own frozen real Gas City
items is complete. Raw Jev matched Opus 5 at maximum effort on 31/32 evaluation
items (96.9%). Seven fresh Claude fallbacks brought final agreement to 32/32,
with 77.9% fewer Claude tokens and 71.2% less classification time. See
[KIND-RESULTS.md](KIND-RESULTS.md) for data, boundary cases and limitations.
This tests the kind-only use case without requiring Julian's original dataset.
The full-build failures in [RESULTS.md](RESULTS.md) remain unresolved as
comparative full-workflow evidence.

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

The paired runner `scripts/jev_kind_ab.py` now implements the live comparison:

1. Freeze the kind rubric and matching title/body inputs before inference.
   Resolve the Opus alias in a separate pilot and pin the observed version for
   evaluation, with the effort setting recorded explicitly.
2. Baseline: classify with the logged-in Claude subscription CLI. Treatment:
   Jev first, then a fresh call to the same Claude classifier for low confidence
   or unclear decisions. Preserve raw Jev output separately from final output.
3. Alternate arm order per case, preserve all input/output/cache usage, and
   include fallback time and tokens. Stop on failure and retain artifacts.
4. Compare raw agreement, final agreement, coverage, repository-label matches,
   Claude tokens, Jev tokens, and complete classification time. Model agreement
   is distinct from independently adjudicated accuracy.

The [completed experiment](KIND-RESULTS.md) contains four pilot pairs and 32
separate evaluation pairs. Each case ran once per arm; there was no tuning on
the evaluation set. Frozen protocol, source hashes, raw responses and token
reconciliation are retained. Full triage execution and repeated measurements
remain separate work; this runner does not make GitHub writes.

The historical backtest runner above still measures only Jev against archived
references. Use the paired runner when measuring live Claude and fallback
usage and latency.

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
