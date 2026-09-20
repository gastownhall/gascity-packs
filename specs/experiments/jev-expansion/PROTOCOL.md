# Expanded Jev comparison, frozen before live inference

40 cases: eight pilot (two per task), 32 evaluation (eight per task). New failure,
finding and duplicate fixtures are authored challenge cases with explicit
expected answers fixed before inference. Kind inputs are a regression subset
of the prior real GitHub dataset, not fresh held-out data. No result is evidence
of general production accuracy. All fixture creation source is retained.

The exact suite is frozen before pilot. Threshold .90 for kinds, findings and
failure routing; .95 floor for pair/candidate decisions. Unclear and
residual-risk findings always require ordinary Claude review. No tuning on the
evaluation set. If pilot requires revision, preserve it and freeze new source
hashes before evaluation. Required quality: no decrease in expected-answer
matches vs baseline and no new dangerous direct routing, lost finding/source,
or omitted duplicate candidate. Report every mismatch even when both models
make it. Passing model agreement alone is insufficient.

Baseline: Claude Opus 5, max effort, subscription CLI, no tools. Treatment:
production helper CLI with Jev 1.13.0; one fresh independent Claude call when
any question requires fallback. Only confident decisions are supplied to that
call; baseline answers are never reused. Questions share one Jev request per
case. Both arms receive identical allowlisted state and criteria. Capture all
raw responses, commands, prompts, token/cache categories, errors and timing.

Run pilot once and evaluation twice per arm with reversed order on the second
repetition. Report unique-case counts separately from repeated measurements.
Also run a downstream report cohort: both arms must produce a source-quoted
report covering every decision. Check exact question coverage, quote provenance,
answer consistency and expected choices. This adds report-generation work to
the measured comparison and can expose overhead hidden by isolated decisions.
Report quality checks do not validate arbitrary prose or the complete Gas City
workflow. No public writes, full build, or code changes by evaluated models.

Use new output directories for every cohort. Stop a cohort on operational
failure, retain it, diagnose and record any retry as a new cohort. Semantic
mismatches do not stop evaluation. Do not pool different task/model/pipeline
cohorts. Jev tokens and Claude tokens are distinct; subscription CLI dollar
estimates are not actual charges. Record actual cost only if billing evidence
is available; otherwise measure tokens and elapsed time without dollar claims.
