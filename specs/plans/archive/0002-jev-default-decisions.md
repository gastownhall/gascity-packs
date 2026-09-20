# Jev decision expansion and default evaluation

Requested: apply PR kind, finding classification/deduplication, failure routing,
and duplicate-issue ranking; improve default speed/token use without observed
quality loss. Claude uses its subscription CLI; Jev uses the existing vault key.

Implement a shared bounded-decision CLI with strict input/response contracts,
retained artifacts, explicit fallback, and auto/off/assist modes. Auto uses Jev
when configured and records an ordinary-LLM route when unconfigured. No helper
executes model-selected commands, drops findings, closes duplicates, or grants
review approval. Integrate into the existing workflow steps, avoiding new agent
steps. Preserve custom-rubric and report-reuse behavior.

Before inference freeze pilot/evaluation datasets and quality criteria for each
new task. Include boundary cases and hostile embedded instructions. Compare
identical inputs/rubrics against pinned subscription Opus at max effort. Track
raw Jev choices separately from final choices, fresh fallbacks, all token/cache
categories and elapsed time. Evaluate the downstream report stage as well as
standalone decisions. Repeat held-out cases; retain every failure and retry.
Re-run existing kind/evidence cohorts separately; do not pool disparate tasks.

Default promotion requires zero observed regression on the frozen executable
quality checks plus improved measured consumption/time. A small passing sample
cannot guarantee universal equivalence. Keep unsupported paths opt-in and
record negative results. Do not infer full Gas City workflow gains from local
classification/report-stage measurements. Record any remaining full-runtime
blocker explicitly.

Progress:
- [x] Bounded helpers and error-path tests
- [x] Workflow integration and formula validation (132 passes; two unchanged baseline timeouts retained)
- [x] Frozen datasets, protocol and expanded paired runner
- [x] Live pilot, evaluation, repeats and existing-cohort reruns (failed evidence baseline retained)
- [x] Downstream output checks, audit, default decision and results


Outcome: added all four integrations. Initial finding/failure pipelines had
paired expected-answer regressions; kind gained no Claude-token reduction when
report generation was included. These remain opt-in. Candidate ordering was
reworked as Noul scoring plus a deterministic evidence handoff, tested on a new
frozen suite, and enabled automatically when configured. Ranking improved
measured component time without observed top-1/source-preservation loss; full
workflow performance and universal quality equivalence remain unproven. See
[results](../../experiments/jev-expansion/RESULTS.md).
