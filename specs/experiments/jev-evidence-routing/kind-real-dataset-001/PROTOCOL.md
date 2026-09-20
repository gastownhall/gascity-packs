# Real kind-triage evaluation

Goal: test Julian's kind-only use case with our own data. His private rubric or
backtest is not a prerequisite. The outcome is measured agreement and routing
behavior on these cases, not reproduction of his particular 96% figure.

Dataset frozen before model inference: 36 public gastownhall/gascity items,
11 issues and 25 PRs. Four pilot items (one per kind); 32 evaluation items
(eight per kind). The exact API queries and selection rule are in suite.json;
candidates-*.json preserve the fetched source projection. Select by issue/PR
number descending within each kind, before examining any model responses.
The latest eligible item per kind is pilot; the next eight are evaluation.
Order items by SHA-256(id) to interleave kinds deterministically.

Only the four published kind categories are evaluated. Existing kind/feature
and kind/enhancement normalize to feature. Items with other kind/* labels or
multiple canonical kinds are excluded. Title/body must be valid and the combined
serialized input at most 100,000 bytes; nothing is truncated. This balanced
sample does not estimate the production prevalence of kinds. Docs items may
be older because selection is by kind. No unlabeled or out-of-taxonomy sample
is included in this first evaluation.

Input to both arms: identical original title and body only. Preserve title
prefixes and quoted text because triage receives them. Existing GitHub labels
are recorded separately and excluded from model requests. No comments, source
code, file diff, repository tools, or author information is provided.

Rubric: gc.kind-question.v1, the pack's existing primary-intent question and
five choices (bug, feature, docs, chore, unclear). Threshold 0.85, frozen before
pilot. No tuning on either cohort. Jev version pinned to jev-1.13.0. Baseline
uses the Claude Max subscription CLI with maximum effort and no tools. The
pilot resolves the opus alias; all four pilot calls resolved to claude-opus-5,
which is pinned for evaluation. CLI version and source hashes are in manifests.

Two arms, fresh processes, counterbalanced within each case:

- Baseline: one Opus kind classification.
- Treatment: one Jev classification; for unclear or confidence below threshold,
  run a fresh Opus classification with the same input and effort. Do not reuse
  the baseline answer or token counts as fallback. Preserve both the raw Jev
  decision and final treatment output.

Record exact request/prompt, output, model, per-model usage, all Claude cache
categories, Jev input/output tokens, elapsed time, and every failure. Stop a
cohort after a failed attempt and diagnose before starting a new immutable run;
never erase or silently retry a failed result. State SHA-256 must match across
arms. No external issue/PR writes are performed.

Primary quality measurement: raw Jev/Opus agreement, confusion matrix, and
agreement by repository kind. Also report final treatment agreement, coverage,
and agreement among decisions routed without Opus. Existing repository labels
are a second imperfect reference, not adjudicated truth. Inspect disagreements
against the frozen title/body and show the ambiguity rather than declaring
Opus or the repository label automatically correct.

Timing covers the local kind-classification pipeline: state materialization,
request/prompt preparation, inference, optional fresh fallback, response
validation and artifact writes before the terminal result. It excludes initial
GitHub snapshot acquisition and does not run the full Gas City triage/comment
workflow. Fresh Claude CLI startup and cache effects are included, and an
already-running worker may have lower overhead. Report total and median times;
record host load, acknowledge uncontrolled network and cache behavior.
