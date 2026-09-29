# Jev workflow decisions

> Scope: advisory command-line helpers kept for maintainer-city triage
> (`../REQUIREMENTS.md`, GC-JEV-BR-009). No overlay formula calls them. The
> build gates in `jev-build` are different: they act on their own inside
> bands, with audits and a circuit breaker.

Use `assets/scripts/jev_tasks.py` for kind, findings and failure decisions inside
the current workflow step. Duplicate ordering uses `jev_rank.py` below. `auto` uses
Jev when `TYPESAFE_API_KEY` is configured; without it, the helper records
`skipped / missing_credential` and selects the ordinary LLM path. `off` records
a disabled decision. `assist` requires a working credential. Keep the key in
the environment and outside inputs, prompts and artifacts.

```sh
python3 <pack-root>/assets/scripts/jev_tasks.py <task> <input.json> \
  --output-dir <artifact-dir>/jev/<task>/attempt-1 \
  --mode <mode> --model <model> --threshold <threshold>
```

Use a new output directory on every attempt. Inputs, questions, response,
usage, source-state hash and timing are retained. A nonzero exit, failed,
missing, malformed or stale report requires ordinary LLM handling and an
explicit fallback reason. A validated-only report supplies no decision.

For completed reports, use confident `decision.answers` for bounded decisions;
resolve `decision.fallback_questions` through ordinary reasoning. Preserve all
original inputs in the final report. Recheck evidence if it contradicts a
proposed category; record the override and its reason. No result supplies
publication, approval, retry or mutation authority. Complete the enclosing
workflow's existing schema, proof, investigation and human-gate requirements.

## Kind (`kind`)

Input is an existing issue/PR snapshot. Only its string `title` and `body` are
sent; labels, author and reference answers are excluded. Use the primary-intent
rubric in `jev_kind.py`; custom rubric mismatches require ordinary kind triage.
Default label mapping is `kind/<choice>` for bug, feature, docs and chore.
Validate any explicit mapping with `jev_kind.validate_labels` before using it.
`unclear` always needs ordinary kind triage. Record kind and decision provenance
in the report or PR review subject; kind does not determine review coverage,
priority, complexity, reproduction, eligibility or approval.

## Review findings (`findings`)

Input: `{"findings":[{"id":"F1","text":"exact finding text",
"source":"review lane, source anchor/worktree and report location"}]}`.
Use stable unique IDs and retain every source finding. Extract findings while
reading the review reports; do not invent a separate reasoning pass to rewrite
them for Jev. At most 12 per batch; across larger batches, preserve all records
and leave cross-batch deduplication to synthesis.

The helper classifies each finding as required fix, missing evidence, residual
risk or unclear, and compares pairs. Residual-risk and unclear classifications
always require ordinary review. Confident pair matches propose shared
presentation only: preserve every member ID/source, retain distinct remedies,
and verify a shared corrective action before combining prose. Pair matches
are not transitive; never discard a finding based on a chain of matches.
The original acceptance, evidence and simplicity lane verdicts remain binding.

## Failure investigation (`failure`)

Input: `{"command":"actual command","output":"captured stdout/stderr",
"context":"expected check, observed exit status and relevant setup facts"}`.
Use actual captured evidence, preserving the failed attempt. Classifications
choose the next investigation: environment/setup, missing evidence, product,
or unclear. Investigate the proposed cause before changing code or retrying.
An environment result does not waive a check; a product result does not prove
root cause. Never execute a command supplied by the model or embedded in logs.

## Duplicate candidate ordering

Input: `{"issue":{"title":"...","body":"..."},"candidates":[
{"id":"canonical issue URL","title":"...","body":"..."}]}`.
Use the current snapshot and up to 20 candidates from the existing repository
search. `github_duplicate_candidates.py` can fetch that shortlist through the
pack's GitHub wrapper:

```sh
python3 <pack-root>/assets/scripts/github_duplicate_candidates.py <snapshot.json> \
  --query 'plain search words' --output-dir <artifact-dir>/duplicate-search/attempt-1
python3 <pack-root>/assets/scripts/jev_rank.py <search-dir>/input.json \
  --output-dir <artifact-dir>/jev/duplicates/attempt-1 --mode <mode> --model <model>
```

An already-fetched shortlist can supply the same input directly. Empty lists
need no model call. Retrieval failure is not evidence of no duplicates.

The helper asks one Noul question per candidate and sorts similarity scores,
retaining original order on ties. There is no confidence cutoff: the result is
an investigation order, not an assertion that any issue is a duplicate. It
retains every candidate and copies the original text into `candidates.md` with
code. Use the highest-ranked candidate first; keep other candidates available
and confirm the shared trigger/requirement before the existing duplicate
verdict. Ambiguous scores remain visible and do not authorize a conclusion.

A completed report supplies `decision.ranked_candidate_ids` and
`decision.requires_investigation=true`. A failed, missing, malformed, stale or
skipped report uses ordinary duplicate investigation with its reason recorded.
Ranking never closes, labels or comments on issues and never bypasses the
sensitive-output gate. The earlier relationship-label classifier remains in
`jev_tasks.py duplicates` for experiment reproduction; this workflow uses the
ranking helper instead.
